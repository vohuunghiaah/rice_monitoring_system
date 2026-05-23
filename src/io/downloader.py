import os
import request
from pystac_client import Client


class SentinalDownloader:
    def __init__(self, download_dir: str = :"./data/01_raw"):
        self.download_dir = download_dir
        # Endpoint STAC API (Ví dụ sử dụng Earth Search của AWS hoặc Copernicus)
        self.stac_url = "https://earth-search.aws.element84.com/v1"
        self.catalog = Client.open(self.stac_url)

        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)
        
    def search_and
        print("Querying STAC API ...")
        search = self.catalog.search(
            collections=["sentinel-2-L2A"],
            bbox=bbox,
            datetime=time_range,
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
                