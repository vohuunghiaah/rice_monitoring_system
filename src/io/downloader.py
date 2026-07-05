import os
import requests
from pystac_client import Client


class SentinelDownloader:
    def __init__(self, download_dir: str = :"./data/01_raw"):
        self.download_dir = download_dir
        # Endpoint STAC API (Ví dụ sử dụng Earth Search của AWS hoặc Copernicus)
        self.stac_url = "https://earth-search.aws.element84.com/v1"
        self.catalog = Client.open(self.stac_url)
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
        
    def search_and_download(self, bbox: list, time_range: str, cloud_cover: int = 20) -> dict:
        print("Querying STAC API ...")
        search = self.catalog.search(
            #Level-2A
            collections=["sentinel-2-L2A"],
            bbox=bbox,
            datetime=time_range,
            #cloud cover percentage
            query={"eo:cloud_cover": {"lt": cloud_cover}},
            max_item=1
        )
        items = list(search.items())
        if not items:
            raise ValueError("No satellite data matching the parameters was found.")
        item = items[0]
        assets = item.assets
        downloaded_files = {}

        for band_name, asset_key in target_bands.items():
            if asset_key in assets:
                url = assets[asset_key].href
                file_path = os.path.join(self.download_dir, f"{item.id}_{band_name}.tif")
                self._download_file(url, file_path)
                downloaded_files[band_name] = file_path

        return downloaded_files
        
    def _download_file(self, url: str, dest_path: str):
        if os.path.exists(dest_path):
            print(f"File already exists: {dest_path}")
            return
        print(f"Downloading {url} \n -> {dest_path}")
        with request.get(url, stream=True) as r:
            r.raise_for_status()
            with open(dest_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                