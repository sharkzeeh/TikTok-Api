from TikTokApi import TikTokApi
import urllib
from bs4 import BeautifulSoup, SoupStrainer
import re
import requests
from time import perf_counter
import os
import csv
from transliterate import translit
import pickle
import argparse


headers = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0'}

def make_dir(dirname):
    current_path = os.getcwd()
    path = os.path.join(current_path, dirname)
    if not os.path.exists(path):
        os.makedirs(path)


def save_single_track(track, dirname, fname):
    with open(f'{dirname}/{fname}.wav' ,'wb') as fh:
        fh.write(track.content)


def download_tracks(dirname, dct):
    length = len(dct.keys())
    for index, (fname, link) in enumerate(dct.items()):
        print (f'Downloading {index + 1} of {length} tracks')
        response = requests.get(link, stream=True)
        save_single_track(response, dirname, fname=fname)
        del response


class Timer:
    'Times your code'
    def __enter__(self):
        self.start = perf_counter()
    def __exit__(self, exc_type, exc_val, traceback):
        t = perf_counter() - self.start
        print("Time elapsed:", f'{t:.3f}')


def str_to_int_views(n_vids: str) -> int:
    typing = lambda n_vids, mult=1: int(float(n_vids[:-1]) * mult)
    n_vids = n_vids.text.split()[0]
    if n_vids.endswith('M'):
        n_vids = typing(n_vids, 1e6)
    elif n_vids.endswith('B'):
        n_vids = typing(n_vids, 1e9)
    elif n_vids.endswith('K'):
        n_vids = typing(n_vids, 1e3)
    else:
        n_vids = int(n_vids)
    return n_vids


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('--num', type=int, default=100)
    opt = parser.parse_args()

    DOWNLOAD_TO = 'download_v2/tracks'
    make_dir(DOWNLOAD_TO)

    # set of track ids
    CORRECT_CACHE = 'download_v2/hrefs_correct_v2.p'
    WRONG_CACHE = 'download_v2/hrefs_wrong_v2.p'

    discovered_ids = set()
    no_vid_count_ids = set()

    # music to track during this particular execution
    tracks_ids_to_download = []
    tracks_ids_never = set()


    if os.path.exists(CORRECT_CACHE) and os.path.exists(WRONG_CACHE):
        with open(CORRECT_CACHE, 'rb') as r_cache, open(WRONG_CACHE, 'rb') as w_cache:
            try:
                print('loading correct tiktok ids ...')
                while True:
                    discovered_ids.add(pickle.load(r_cache))
            except EOFError:
                print('loaded correct tiktok ids!')

            try:
                print('loading wrong tiktok ids ...')
                while True:
                    no_vid_count_ids.add(pickle.load(w_cache))
            except EOFError:
                print('loaded wrong tiktok ids!')


    with Timer():
        api = TikTokApi()
        results = opt.num
        trending = api.trending(count=results)
        assert(len(trending) == opt.num)


    with open(CORRECT_CACHE, 'ab') as r_cache, open(WRONG_CACHE, 'ab') as w_cache:
        trending = list(filter(lambda t: t['id'] not in no_vid_count_ids, trending))
        for tiktok in trending:

            tt_id = tiktok['id']
            track = tiktok['music']
            track_id = track['id']

            url_track_part = track['playUrl']
            title_quo = urllib.parse.quote(track['title']) # IRI to URI
            final_url_paste = title_quo + '-' + track_id
            url = f'https://www.tiktok.com/music/{final_url_paste}?lang=en'
            html = requests.get(url, headers=headers).text
            soup = BeautifulSoup(html, 'html.parser')
            n_vids = soup.find('h2', {'class': 'jsx-450795707 jsx-597743636 description'}) # vids count

            try:
                n_vids = str_to_int_views(n_vids)
            except AttributeError:
                if tt_id not in tracks_ids_never:
                    print('no VIDEO COUNT for', tt_id, tiktok['desc'])
                    pickle.dump(tt_id, w_cache)
                    tracks_ids_never.add(tt_id)
                    continue

            if tt_id not in discovered_ids:
                tracks_ids_to_download.append(tt_id)
                pickle.dump(tt_id, r_cache)

                # or use these 2 lines of code to download on the fly
                response = requests.get(url_track_part, stream=True)
                save_name = str(tt_id) + '_' + str(n_vids)
                save_single_track(response, DOWNLOAD_TO, fname=save_name)


    print('total new downloads:', len(tracks_ids_to_download))