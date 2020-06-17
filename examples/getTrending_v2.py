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
import socket
import librosa
import sys
import numpy as np

HOST = '192.168.56.2'
PORT = 65432
HEADERSIZE = 10

headers = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:52.0) Gecko/20100101 Firefox/52.0'}

def make_dir(dirname):
    current_path = os.getcwd()
    path = os.path.join(current_path, dirname)
    if not os.path.exists(path):
        os.makedirs(path)


def save_single_track(track, dirname, fname):
    with open(f"{dirname}/{fname}.wav" ,'wb') as fh:
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

def extract_features(fn, bands=60, frames=41):
    def _windows(data, window_size):
        start = 0
        while start < len(data):
            yield int(start), int(start + window_size)
            start += (window_size // 2)
            
    window_size = 512 * (frames - 1)
    features, labels = [], []
    segment_log_specgrams, segment_labels = [], []
    sound_clip,sr = librosa.load(f'{DOWNLOAD_TO}/{fn}.wav')
    label = int(int(fn.split('_')[1])>50000)
    for (start,end) in _windows(sound_clip,window_size):
        if len(segment_labels) > 30:
            break   
        if(len(sound_clip[start:end]) == window_size):
            signal = sound_clip[start:end]
            melspec = librosa.feature.melspectrogram(signal,n_mels=bands)
            logspec = librosa.amplitude_to_db(melspec)
            logspec = logspec.T.flatten()[:, np.newaxis].T
            segment_log_specgrams.append(logspec)
            segment_labels.append(label)
        
    segment_log_specgrams = np.asarray(segment_log_specgrams).reshape(
        len(segment_log_specgrams),bands,frames,1)
    segment_features = np.concatenate((segment_log_specgrams, np.zeros(
        np.shape(segment_log_specgrams))), axis=3)
    for i in range(len(segment_features)): 
        segment_features[i, :, :, 1] = librosa.feature.delta(
            segment_features[i, :, :, 0])
    
    print(segment_features.shape)
    
    if len(segment_features) > 0: # check for empty segments 
        features.append(segment_features.tolist())
        labels.append(segment_labels)
    return features, labels

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

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        with open(CORRECT_CACHE, 'ab') as r_cache, open(WRONG_CACHE, 'ab') as w_cache:
            trending = list(filter(lambda t: t['id'] not in no_vid_count_ids, trending))
            for tiktok in trending:
                #print(tiktok['music']['title'])
                tt_id = tiktok['id']
                track = tiktok['music']
                track_id = track['id']

                url_track_part = track['playUrl']
                title_quo = urllib.parse.quote(track['title']) # IRI to URI
                final_url_paste = title_quo + '-' + track_id
                
                url = f'https://www.tiktok.com/music/{final_url_paste}?lang=en'
                html = requests.get(url.replace('%', '-'), headers=headers).text
                soup = BeautifulSoup(html, 'html.parser')
                n_vids = soup.find('h2', {'class': 'jsx-1095438058 description'}) # vids count
                try:
                    n_vids = str_to_int_views(n_vids)
                except AttributeError:
                    if tt_id not in tracks_ids_never:
                        print('no VIDEO COUNT for', tt_id, tiktok['desc'])
                        pickle.dump(tt_id, w_cache)
                        continue

                if tt_id not in discovered_ids:
                    tracks_ids_to_download.append(tt_id)
                    pickle.dump(tt_id, r_cache)

                    response = requests.get(url_track_part, stream=True)
                    save_name = str(tt_id) + '_' + str(n_vids)
                    save_single_track(response, DOWNLOAD_TO, fname=save_name)
                    try:
                        features, labels = extract_features(save_name)
                    except: 
                        continue
                    data = {'id': tt_id, 'features': features, "labels": labels}
                    msg = pickle.dumps(data)
                    msg = bytes(f"{len(msg):<{HEADERSIZE}}", "utf-8")+msg
                    s.send(msg)
                    responce = s.recv(1024)

                    print('total new downloads:', len(tracks_ids_to_download))



