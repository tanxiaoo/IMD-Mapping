"""Export Earth Engine images to Google Drive and download them into ``output/``.

A predicted raster is too large for a direct download (``getDownloadURL`` caps
at tens of MB; a 10 m Milan map is ~200 MB), so it goes through a batch export
to Drive. This module closes the loop: it submits the export, waits for it,
finds the file the task wrote and saves it at the path the notebook reads.

    from gee_export import start_export, wait_and_download

    jobs = [start_export(img_rf,  RF_RASTER_PATH,  region=aoi_geom, crs='EPSG:32632'),
            start_export(img_svr, SVR_RASTER_PATH, region=aoi_geom, crs='EPSG:32632')]
    wait_and_download(jobs)

All tasks are submitted before any is waited on, so Earth Engine runs them in
parallel. The Drive file name is the stem of the local path.

Design decisions, each fixing a way the manual or copy-pasted versions went
wrong:

- **The file is found through its task, not by name alone.** The same name is
  exported by every run of 01b/01d (one per composite method) and by every
  rerun, so Drive holds several files with it. The search is restricted to the
  folder the task reports writing to, and to files created after the task was.
- **The download never leaves a partial file at the final path.** It writes
  to ``<path>.part`` and renames on success, so an interrupted download cannot
  be mistaken for a finished raster on the next run.
- **There is no "skip if the file exists".** Running the export cell means the
  model was just refitted; reusing an older raster would pair new metadata with
  an old map. Do not rerun the cell if you do not want a new export.
- **Tiled exports are merged.** Earth Engine splits a large GeoTIFF into
  ``<name>-<row>-<col>.tif`` tiles; they are mosaicked back into one file.

Drive access reuses the Earth Engine credentials. ``earthengine authenticate``
requests the Drive scope in current versions of ``earthengine-api``; if a
download fails with a permissions error, the stored credentials predate that,
and ``earthengine authenticate --force`` replaces them.
"""

import os
import re
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ee

DRIVE_FOLDER = "GEE_exports"
POLL_SECONDS = 30
_DONE = ("COMPLETED", "FAILED", "CANCELLED")


@dataclass
class Export:
    """A submitted export and where its result should land locally."""

    task: ee.batch.Task
    name: str
    out_path: Path


def start_export(image, out_path, *, region, crs, scale=10, folder=DRIVE_FOLDER):
    """Submit a GeoTIFF export of ``image`` to Drive; return an :class:`Export`.

    ``out_path`` is where :func:`wait_and_download` will save the file. Its
    stem is used as the Drive file name and the task description.
    """
    out_path = Path(out_path)
    name = out_path.stem
    task = ee.batch.Export.image.toDrive(
        image=image, description=name[:100], folder=folder,
        fileNamePrefix=name, region=region, scale=scale, crs=crs,
        maxPixels=1e10, fileFormat="GeoTIFF")
    task.start()
    print(f"  export started: {name} (task {task.id})")
    return Export(task=task, name=name, out_path=out_path)


def wait_and_download(exports, poll_seconds=POLL_SECONDS):
    """Wait for every export, downloading each as soon as it completes.

    Raises after the others have finished if any task failed or was
    cancelled, so one failure does not discard rasters that did export.
    """
    pending = list(exports)
    failed = []
    drive = None
    t0 = time.time()
    while pending:
        still = []
        for job in pending:
            status = job.task.status()
            state = status["state"]
            if state == "COMPLETED":
                drive = drive or _drive_service()
                _download(drive, job, status)
            elif state in _DONE:
                failed.append(f"{job.name}: {state} {status.get('error_message', '')}")
                print(f"  {job.name}: {state}")
            else:
                still.append(job)
        pending = still
        if pending:
            waiting = ", ".join(j.name for j in pending)
            print(f"  [{(time.time() - t0) / 60:4.1f} min] waiting for {waiting}")
            time.sleep(poll_seconds)
    if failed:
        raise RuntimeError("Export failed:\n  " + "\n  ".join(failed))


def export_and_download(image, out_path, **kwargs):
    """Export one image and download it; :func:`start_export` arguments."""
    wait_and_download([start_export(image, out_path, **kwargs)])


def _drive_service():
    from googleapiclient.discovery import build

    creds = ee.data.get_persistent_credentials()
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def _find_files(drive, job, status):
    """Return the Drive files this task wrote: one file, or its tiles."""
    from googleapiclient.errors import HttpError

    uris = " ".join(status.get("destination_uris") or [])
    folder = re.search(r"folders/([\w-]+)", uris)
    created = datetime.fromtimestamp(status["creation_timestamp_ms"] / 1000, timezone.utc)
    # Allow for clock difference between the two services.
    since = (created - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%S")

    query = [f"name contains '{job.name}'", "trashed = false",
             f"createdTime > '{since}'"]
    if folder:
        query.append(f"'{folder.group(1)}' in parents")
    pattern = re.compile(re.escape(job.name) + r"(-\d+-\d+)?\.tif")

    # A completed task's file can take a few seconds to become listable.
    for attempt in range(6):
        try:
            resp = drive.files().list(
                q=" and ".join(query), fields="files(id, name, createdTime)",
                pageSize=100).execute()
        except HttpError as e:
            if e.resp.status == 403:
                raise RuntimeError(
                    "Drive refused access. The Earth Engine credentials on this "
                    "machine lack the Drive scope; run\n"
                    "    earthengine authenticate --force\n"
                    "and restart the kernel.") from e
            raise
        files = [f for f in resp.get("files", []) if pattern.fullmatch(f["name"])]
        if files:
            return sorted(files, key=lambda f: f["name"])
        time.sleep(5 * (attempt + 1))
    where = f"folder {folder.group(1)}" if folder else "Drive"
    raise RuntimeError(f"{job.name}: task completed but no {job.name}*.tif found in {where}.")


def _download_file(drive, file_id, path):
    from googleapiclient.http import MediaIoBaseDownload

    with open(path, "wb") as fh:
        downloader = MediaIoBaseDownload(
            fh, drive.files().get_media(fileId=file_id), chunksize=64 * 1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()


def _download(drive, job, status):
    files = _find_files(drive, job, status)
    job.out_path.parent.mkdir(parents=True, exist_ok=True)
    part = job.out_path.with_name(job.out_path.name + ".part")
    try:
        if len(files) == 1:
            _download_file(drive, files[0]["id"], part)
        else:
            _download_tiles(drive, files, part)
        os.replace(part, job.out_path)
    finally:
        if part.exists():
            part.unlink()
    size_mb = job.out_path.stat().st_size / 1e6
    print(f"  {job.name}: downloaded {size_mb:.0f} MB -> {job.out_path}")


def _download_tiles(drive, files, path):
    import rasterio
    from rasterio.merge import merge

    with tempfile.TemporaryDirectory(dir=path.parent) as tmp:
        tiles = []
        for f in files:
            tile = Path(tmp) / f["name"]
            _download_file(drive, f["id"], tile)
            tiles.append(tile)
        sources = [rasterio.open(t) for t in tiles]
        try:
            mosaic, transform = merge(sources)
            profile = sources[0].profile
            profile.update(height=mosaic.shape[1], width=mosaic.shape[2],
                           transform=transform, compress="deflate", BIGTIFF="IF_SAFER")
            with rasterio.open(path, "w", **profile) as dst:
                dst.write(mosaic)
        finally:
            for s in sources:
                s.close()
