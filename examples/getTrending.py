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
    if not os.path.exists(path):# or not os.listdir(path):
        os.makedirs(path)

def save_single_track(track, dirname, fname):
    with open(f'{dirname}/{fname}.mp3' ,'wb') as fh:
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

def formatter(s: str) -> str:
    s = translit(s, "ru", reversed=True)
    s = re.sub("'", '', s)
    s = re.sub(' ', '_', s)
    s = re.sub('/', '', s)
    return s


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('--num', type=int, default=100)
    opt = parser.parse_args()


    DOWNLOAD_TO = 'download'
    make_dir(DOWNLOAD_TO)
    h_tracks = {} # currently running dict; starts out empty each new run

    CORRECT_CACHE = 'already_there.p'
    WRONG_CACHE = 'missed.p'
    AT_to_ref = {} #  AT == AuthorTrack
    WRONG_ids = set()
    if os.path.exists(CORRECT_CACHE):
        with open(CORRECT_CACHE, 'rb') as cache, open(WRONG_CACHE, 'rb') as w_cache:
            try:
                print('loading correct records ...')
                while True:
                    AT_to_ref.update(pickle.load(cache))
            except EOFError:
                print('loaded correct records!')

            try:
                print('loading wrong records ...')
                while True:
                    WRONG_ids.add(pickle.load(w_cache))
            except EOFError:
                print('loaded wrong records!')


    with Timer():
        api = TikTokApi()
        results = opt.num
        trending = api.trending(count=results)


    with open('download.csv', 'a') as csvfile, open(CORRECT_CACHE, 'ab') as cache, open(WRONG_CACHE, 'ab') as w_cache:
        fieldnames = ['title', 'author', 'n_vids', 'mp3_fname']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not csvfile.tell():
            writer.writeheader()
            print('writing for the first time!')
        else:
            print('continue writing!')
        assert(len(trending) == opt.num)
        trending = list(filter(lambda tt: tt['id'] not in WRONG_ids, trending))
        for tiktok in trending:
            # if tiktok['id'] in WRONG_ids:
            #     continue
            track = tiktok['music']
            title = track['title']

            # removing `original sound` tiktoks
            if 'оригинальный звук' in title or 'original sound' in title:
                print(tiktok['id'], title)
                pickle.dump(tiktok['id'], w_cache)
                continue

            url_track_part = track['playUrl']
            title_quo = urllib.parse.quote(track['title']) # IRI to URI
            final_url_paste = title_quo + '-' + track['id']
            url = f'https://www.tiktok.com/music/{final_url_paste}?lang=en'
            html = requests.get(url, headers=headers).text
            soup = BeautifulSoup(html, 'html.parser')
            n_vids = soup.find('h2', {'class': 'jsx-450795707 jsx-597743636 description'}) # vids count

            try:
                n_vids = str_to_int_views(n_vids)
            except AttributeError:
                print('no VIDEO COUNT for', tiktok['id'], tiktok['desc'])
                pickle.dump(tiktok['id'], w_cache)
                continue

            try:
                if '-' in title:
                    sp = title.split('-')
                    author = sp[0].strip()
                    title = sp[1].strip()
                else:
                    author = track['authorName']
            except KeyError:
                print('no AUTHOR for', tiktok['id'], tiktok['desc'])
                continue

            title = formatter(title)
            author = formatter(author)
            author_track = author + '-' + title

            if author_track not in AT_to_ref:
                var = {author_track: url_track_part}
                AT_to_ref.update(var)

                # DOWNLOAD PART
                # # for download after all (see the very bottom line `download_tracks(...)`)
                h_tracks.update(var)

                # or use these 2 lines of code to download on the fly
                response = requests.get(url_track_part, stream=True)
                save_single_track(response, DOWNLOAD_TO, fname=author_track)

                pickle.dump(var, cache)
                mp3_file = author_track + '.mp3'
                writer.writerow({'title': title, 'author': author, 'n_vids': n_vids, 'mp3_fname': mp3_file})
                out = f"{author} - {title}, total n_vids: {n_vids}"
                print(out)

    print('total new downloads:', len(list(h_tracks)))
    # download_tracks(DOWNLOAD_TO, h_tracks)