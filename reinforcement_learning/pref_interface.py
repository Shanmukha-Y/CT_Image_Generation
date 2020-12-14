#!/usr/bin/env python

"""
A simple CLI-based interface for querying the user about segment preferences.
"""

import logging
import queue
import time
from itertools import combinations
from multiprocessing import Queue
from random import shuffle

import easy_tf_log
import numpy as np

# from utils import VideoRenderer


class PrefInterface:

    def __init__(self, synthetic_prefs, max_segs, log_dir): # synthetic_prefs ???
        self.vid_q = Queue()
        if not synthetic_prefs:
            pass
            ### start your custom interface 
#             self.renderer = VideoRenderer(vid_queue=self.vid_q,
#                                           mode=VideoRenderer.restart_on_get_mode,
#                                           zoom=4)
        else:
            self.renderer = None
        self.synthetic_prefs = synthetic_prefs
        self.seg_idx = 0
        self.segments = []
        self.tested_segment = set()  # For O(1) lookup
        self.max_segs = max_segs
        easy_tf_log.set_dir(log_dir)

    def stop_renderer(self):
        if self.renderer:
            self.renderer.stop()

    def run(self, seg_pipe, pref_pipe):
        while len(self.segments) < 8: #2: receive 8 segements at a time
            print("Preference interface waiting for segments")
            time.sleep(5.0)
            self.recv_segments(seg_pipe)

        while True:
#             seg_pair = None
            while seg_eight is None:
                try:
                    seg_eight = self.sample_seg_eight()
                    # assert their bottom vects equality
                except IndexError:
                    print("Preference interface ran out of untested segments;"
                          "waiting...")
                    # If we've tested all possible pairs of segments so far,
                    # we'll have to wait for more segments
                    time.sleep(1.0)
                    self.recv_segments(seg_pipe)
#             s1, s2 = seg_pair
            
            logging.debug("Querying preference for segments block %s ",
                          seg_eight)
            
            segment_idxs = list(range(seg_eight*8, seg_eight*8 + 8))
            ### write code for displaying the eight segments self.segments[segment_idxs]
            ### and getting the feedback
            
            possible_pairs = combinations(segment_idxs, 2)
            for i1, i2 in possible_pairs:
                s1, s2 = self.segments[i1], self.segments[i2]
                ### write code for identifying a pref for s1, s2
                if (s1.better_than_linear and not s2.better_than_linear) or \
                    (not s1.worse_torso and s2.worse_torso):
                    pref = (1.0, 0.0)
                elif (not s1.better_than_linear and s2.better_than_linear) or \
                    (s1.worse_torso and not s2.worse_torso):
                    pref = (0.0, 1.0)
                else:
                    pref = (0.5, 0.5)

#             if not self.synthetic_prefs:
#                 pref = self.ask_user(s1, s2)
#             else:
#                 if sum(s1.rewards) > sum(s2.rewards):
#                     pref = (1.0, 0.0)
#                 elif sum(s1.rewards) < sum(s2.rewards):
#                     pref = (0.0, 1.0)
#                 else:
#                     pref = (0.5, 0.5)

            if pref is not None:
                # We don't need the rewards from this point on, so just send
                # the frames  ###? because the rewards are known by reward classifier???
                pref_pipe.put((s1.frames, s2.frames, pref))
            # If pref is None, the user answered "incomparable" for the segment
            # pair. The pair has been marked as tested; we just drop it.

            self.recv_segments(seg_pipe)

    def recv_segments(self, seg_pipe):
        """
        Receive segments from `seg_pipe` into circular buffer `segments`.
        """
        max_wait_seconds = 0.5
        start_time = time.time()
        n_recvd = 0
        while time.time() - start_time < max_wait_seconds:
            try:
                segment = seg_pipe.get(block=True, timeout=max_wait_seconds)
            except queue.Empty:
                return
            if len(self.segments) < self.max_segs:
                self.segments.append(segment)
            else:
                self.segments[self.seg_idx] = segment
                self.seg_idx = (self.seg_idx + 1) % self.max_segs
            n_recvd += 1
        easy_tf_log.tflog('segment_idx', self.seg_idx)
        easy_tf_log.tflog('n_segments_rcvd', n_recvd)
        easy_tf_log.tflog('n_segments', len(self.segments))

    def sample_seg_eight(self):
        """
        Sample a random pair of segments which hasn't yet been tested.
        """
        segment_idxs_blocks = list(range(len(self.segments) / 8)) ## assert multiple of 8
#         shuffle(segment_idxs)
        #choose one group of 8 ; iterate all possible combinations of that grp below
        possible_segments_blocks = combinations(segment_idxs_blocks, 1)
        for s in possible_segments_blocks:
            first_seg = self.segments[s*8]
            if first_seg.hash not in self.tested_segment:
                self.tested_segment.add(first_seg.hash)
                return s
        raise IndexError("No segment blocks yet untested")

    def ask_user(self, s1, s2):
        vid = []
        seg_len = len(s1)
        for t in range(seg_len):
            border = np.zeros((84, 10), dtype=np.uint8)
            # -1 => show only the most recent frame of the 4-frame stack
            frame = np.hstack((s1.frames[t][:, :, -1],
                               border,
                               s2.frames[t][:, :, -1]))
            vid.append(frame)
        n_pause_frames = 7
        for _ in range(n_pause_frames):
            vid.append(np.copy(vid[-1]))
        self.vid_q.put(vid)

        while True:
            print("Segments {} and {}: ".format(s1.hash, s2.hash))
            choice = input()
            # L = "I prefer the left segment"
            # R = "I prefer the right segment"
            # E = "I don't have a clear preference between the two segments"
            # "" = "The segments are incomparable"
            if choice == "L" or choice == "R" or choice == "E" or choice == "":
                break
            else:
                print("Invalid choice '{}'".format(choice))

        if choice == "L":
            pref = (1.0, 0.0)
        elif choice == "R":
            pref = (0.0, 1.0)
        elif choice == "E":
            pref = (0.5, 0.5)
        elif choice == "":
            pref = None

        self.vid_q.put([np.zeros(vid[0].shape, dtype=np.uint8)])

        return pref