import warnings

import numpy as np
from scipy.io import wavfile
import scipy.signal
from scipy.signal import slepian  # AKA DPSS, window used for FFT
from matplotlib.mlab import specgram

from . import evfuncs, koumura


class WindowError(Exception):
    pass


class Spectrogram:
    """class for making spectrograms.
    Abstracts out function calls so user just has to put spectrogram parameters
    in YAML config file.
    """

    def __init__(self,
                 ref=None,
                 nperseg=None,
                 noverlap=None,
                 freq_cutoffs=None,
                 window=None,
                 filter_func=None,
                 spect_func=None,
                 log_transform_spect=True):
        """Spectrogram.__init__ function
        
        Parameters
        ----------
        ref : str
            {'tachibana','koumura'}
            Use spectrogram parameters from a reference.
            'tachibana' uses spectrogram parameters from [1]_,
            'koumura' uses spectrogram parameters from [2]_.
        nperseg : int
            numper of samples per segment for FFT, e.g. 512
        noverlap : int
            number of overlapping samples in each segment

        Either ref or nperseg and noverlap are required for __init__

        Other Parameters
        ----------------
        freq_cutoffs : two-element list of integers
            limits of frequency band to keep, e.g. [1000,8000]
            Spectrogram.make keeps the band:
                freq_cutoffs[0] >= spectrogram > freq_cutoffs[1]
            Default is None.
        window : str
            window to apply to segments
            valid strings are 'Hann', 'dpss', None
            Hann -- Uses np.Hanning with parameter M (window width) set to value of nperseg
            dpss -- Discrete prolate spheroidal sequence AKA Slepian.
                Uses scipy.signal.slepian with M parameter equal to nperseg and
                width parameter equal to 4/nperseg, as in [2]_.
            Default is None.
        filter_func : str
            filter to apply to raw audio. valid strings are 'diff' or None
            'diff' -- differential filter, literally np.diff applied to signal as in [1]_.
            Default is None.
        spect_func : str
            which function to use for spectrogram.
            valid strings are 'scipy' or 'mpl'.
            'scipy' uses scipy.signal.spectrogram,
            'mpl' uses matplotlib.matlab.specgram.
            Default is 'scipy'.
        log_transform_spect : bool
            if True, applies np.log10 to spectrogram to increase range.
            Default is True.

        References
        ----------
        .. [1] Tachibana, Ryosuke O., Naoya Oosugi, and Kazuo Okanoya. "Semi-
        automatic classification of birdsong elements using a linear support vector
         machine." PloS one 9.3 (2014): e92584.

        .. [2] Koumura, Takuya, and Kazuo Okanoya. "Automatic recognition of element
        classes and boundaries in the birdsong with variable sequences."
        PloS one 11.7 (2016): e0159188.
        """

        # check for 'reference' parameter first since it takes precedence
        if ref is not None:
            if ref not in ('tachibana', 'koumura'):
                raise ValueError('{} is not a valid value for reference argument'.
                                 format(ref))
            # warn if called with 'ref' and with other params
            if any(param is not None
                   for param in [nperseg,
                                 noverlap,
                                 freq_cutoffs,
                                 filter_func,
                                 spect_func]):
                warnings.warn('Spectrogram class received ref '
                              'parameter but also received other parameters, '
                              'will over-write those with defaults for reference.')
            else:
                if ref == 'tachibana':
                    self.nperseg = 256
                    self.noverlap = 192
                    self.window = np.hanning(self.nperseg) #Hann window
                    self.freqCutoffs = None
                    self.filterFunc = 'diff'
                    self.spectFunc = 'mpl'
                    self.logTransformSpect = False  # see tachibana feature docs
                    self.ref = ref
                elif ref == 'koumura':
                    self.nperseg = 512
                    self.noverlap = 480
                    self.window = slepian(self.nperseg, 4 / self.nperseg) #dpss
                    self.freqCutoffs = [1000, 8000]
                    self.filterFunc = None
                    self.spectFunc = 'scipy'
                    self.logTransformSpect = True
                    self.ref = ref
                else:
                    raise ValueError('{} is not a valid value for \'ref\' argument. '
                                     'Valid values: {\'tachibana\',\'koumura\',None}'
                                     .format(ref))

        elif ref is None:
            if nperseg is None:
                raise ValueError('nperseg requires a value for Spectrogram.__init__')
            if noverlap is None:
                raise ValueError('noverlap requires a value for Spectrogram.__init__')
            if spect_func is None:
                # switch to default
                # can't have in args list because need to check above for
                # conflict with default spectrogram functions for each ref
                spect_func = 'scipy'
            if type(nperseg) != int:
                raise TypeError('type of nperseg must be int, but is {}'.
                                 format(type(nperseg)))
            else:
                self.nperseg = nperseg

            if type(noverlap) != int:
                raise TypeError('type of noverlap must be int, but is {}'.
                                 format(type(noverlap)))
            else:
                self.noverlap = noverlap

            if window is not None and type(window) != str:
                raise TypeError('type of window must be str, but is {}'.
                                 format(type(window)))
            else:
                if window not in ['Hann','dpss',None]:
                    raise ValueError('{} is not a valid specification for window'.
                                     format(window))
                else:
                    if window == 'Hann':
                        self.window = np.hanning(self.nperseg)
                    elif window == 'dpss':
                        self.window = slepian(self.nperseg, 4 / self.nperseg)
                    elif window is None:
                        self.window = None

            if type(freq_cutoffs) != list:
                raise TypeError('type of freq_cutoffs must be list, but is {}'.
                                 format(type(freq_cutoffs)))
            elif len(freq_cutoffs) != 2:
                raise ValueError('freq_cutoffs list should have length 2, but length is {}'.
                                 format(len(freq_cutoffs)))
            elif not all([type(val) == int for val in freq_cutoffs]):
                raise ValueError('all values in freq_cutoffs list must be ints')
            else:
                self.freqCutoffs = freq_cutoffs

            if filter_func is not None and type(filter_func) != str:
                raise TypeError('type of filter_func must be str, but is {}'.
                                 format(type(filter_func)))
            elif filter_func not in ['diff',None]:
                raise ValueError('string \'{}\' is not valid for filter_func. '
                                 'Valid values are: \'diff\' or None.'.
                                 format(filter_func))
            else:
                self.filterFunc = filter_func

                if type(spect_func) != str:
                    raise TypeError('type of spect_func must be str, but is {}'.
                                     format(type(spect_func)))
                elif spect_func not in ['scipy','mpl']:
                    raise ValueError('string \'{}\' is not valid for filter_func. '
                                     'Valid values are: \'scipy\' or \'mpl\'.'.
                                     format(spect_func))
                else:
                    self.spectFunc = spect_func

                if type(log_transform_spect) is not bool:
                    raise ValueError('Value for log_transform_spect is {}, but'
                                     ' it must be bool.'
                                     .format(type(log_transform_spect)))
                else:
                    self.logTransformSpect = log_transform_spect

    def make(self,
             raw_audio,
             samp_freq):
        """makes spectrogram using assigned properties
        
        Parameters
        ----------
        raw_audio : 1-d numpy array
            raw audio waveform
        samp_freq : integer scalar
            sampling frequency in Hz

        Returns
        -------
        spect : 2-d numpy array
        freq_bins : 1-d numpy array
        time_bins : 1-d numpy array
        """

        if self.filterFunc == 'diff':
            raw_audio = np.diff(raw_audio)  # differential filter_func, as applied in Tachibana Okanoya 2014

        try:  # try to make spectrogram
            if self.spectFunc == 'scipy':
                if self.window is not None:
                        freq_bins, time_bins, spect = scipy.signal.spectrogram(raw_audio,
                                                                               samp_freq,
                                                                               window=self.window,
                                                                               nperseg=self.nperseg,
                                                                               noverlap=self.noverlap)
                else:
                    freq_bins, time_bins, spect = scipy.signal.spectrogram(raw_audio,
                                                                           samp_freq,
                                                                           nperseg=self.nperseg,
                                                                           noverlap=self.noverlap)

            elif self.spectFunc == 'mpl':
                # note that the matlab specgram function returns the STFT by default
                # whereas the default for the matplotlib.mlab version of specgram
                # returns the PSD. So to get the behavior of matplotlib.mlab.specgram
                # to match, mode must be set to 'complex'

                # I think I determined empirically at one point (by staring at single
                # cases) that mlab.specgram gave me values that were closer to Matlab's
                # specgram function than scipy.signal.spectrogram
                # Matlab's specgram is what Tachibana used in his original feature
                # extraction code. So I'm maintaining the option to use it here.

                # 'mpl' is set to return complex frequency spectrum,
                # not power spectral density,
                # because some tachibana features (based on CUIDADO feature set)
                # need to use the freq. spectrum before taking np.abs or np.log10
                if self.window is not None:
                    spect, freq_bins, time_bins = specgram(raw_audio,
                                                           NFFT=self.nperseg,
                                                           Fs=samp_freq,
                                                           window=self.window,
                                                           noverlap=self.noverlap,
                                                           mode='complex')
                else:
                    spect, freq_bins, time_bins = specgram(raw_audio,
                                                           NFFT=self.nperseg,
                                                           Fs=samp_freq,
                                                           noverlap=self.noverlap,
                                                           mode='complex')
        except ValueError as err:  # if `try` to make spectrogram raised error
            if str(err) == 'window is longer than input signal':
                raise WindowError()
            else:  # unrecognized error
                raise

        if self.logTransformSpect:
            spect = np.log10(spect)  # log transform to increase range

        #below, I set freq_bins to >= freq_cutoffs
        #so that Koumura default of [1000,8000] returns 112 freq. bins
        if self.freqCutoffs is not None:
            f_inds = np.nonzero((freq_bins >= self.freqCutoffs[0]) &
                                (freq_bins < self.freqCutoffs[1]))[0] #returns tuple
            freq_bins = freq_bins[f_inds]
            spect = spect[f_inds, :]

        #flip spect and freq_bins so lowest frequency is at 0 on y axis when plotted
        spect = np.flipud(spect)
        freq_bins = np.flipud(freq_bins)
        return spect, freq_bins, time_bins


def compute_amp(spect):
    """
    compute amplitude of spectrogram
    Assumes the values for frequencies are power spectral density (PSD).
    Sums PSD for each time bin, i.e. in each column.
    Inputs:
        spect -- output from spect_from_song
    Returns:
        amp -- amplitude
    """

    return np.sum(spect,axis=0)

def segment_song(amp,
                 time_bins,
                 segment_params=None):
    """Divides songs into segments based on threshold crossings of amplitude.
    Returns onsets and offsets of segments, corresponding (hopefully) to syllables in a song.
    Parameters
    ----------
    amp : 1-d numpy array
        amplitude of power spectral density. Returned by compute_amp.
    time_bins : 1-d numpy array
        time in s, must be same length as log amp. Returned by Spectrogram.make.
    segment_params : dict
        with the following keys
            threshold : int
                value above which amplitude is considered part of a segment. default is 5000.
            min_syl_dur : float
                minimum duration of a segment. default is 0.02, i.e. 20 ms.
            min_silent_dur : float
                minimum duration of silent gap between segment. default is 0.002, i.e. 2 ms.

    Returns
    -------
    onsets : 1-d numpy array
    offsets : 1-d numpy array
        arrays of onsets and offsets of segments.
        
    So for syllable 1 of a song, its onset is onsets[0] and its offset is offsets[0].
    To get that segment of the spectrogram, you'd take spect[:,onsets[0]:offsets[0]]
    """

    if segment_params is None:
        segment_params = {'threshold' : 5000,
                          'min_syl_dur' : 0.2,
                          'min_silent_dur' : 0.02}
    above_th = amp > segment_params['threshold']
    h = [1, -1] 
    above_th_convoluted = np.convolve(h,above_th) # convolving with h causes:
    # +1 whenever above_th changes from 0 to 1
    onsets = time_bins[np.nonzero(above_th_convoluted > 0)]
    # and -1 whenever above_th changes from 1 to 0
    offsets = time_bins[np.nonzero(above_th_convoluted < 0)]
    
    #get rid of silent intervals that are shorter than min_silent_dur
    silent_gap_durs = onsets[1:] - offsets[:-1] # duration of silent gaps
    keep_these = np.nonzero(silent_gap_durs > segment_params['min_silent_dur'])
    onsets = onsets[keep_these]
    offsets = offsets[keep_these]
    
    #eliminate syllables with duration shorter than min_syl_dur
    syl_durs = offsets - onsets
    keep_these = np.nonzero(syl_durs > segment_params['min_syl_dur'])
    onsets = onsets[keep_these]
    offsets = offsets[keep_these]

    return onsets, offsets

class syllable:
    """
    syllable object, returned by make_syl_spect.
    Properties
    ----------
    syl_audio : 1-d numpy array
        raw waveform from audio file
    sampfreq : integer
        sampling frequency in Hz as determined by scipy.io.wavfile function
    spect : 2-d m by n numpy array
        spectrogram as computed by Spectrogram.make(). Each of the m rows is a frequency bin,
        and each of the n columns is a time bin. Value in each bin is power at that frequency and time.
    nfft : integer
        number of samples used for each FFT
    overlap : integer
        number of samples that each consecutive FFT window overlapped
    time_bins : 1d vector
        values are times represented by each bin in s
    freq_bins : 1d vector
        values are power spectral density in each frequency bin
    index: int
        index of this syllable in song.syls.labels
    label: int
        label of this syllable from song.syls.labels
    """
    def __init__(self,
                 syl_audio,
                 samp_freq,
                 spect,
                 nfft,
                 overlap,
                 freq_cutoffs,
                 freq_bins,
                 time_bins,
                 index,
                 label):
        self.sylAudio = syl_audio
        self.sampFreq = samp_freq
        self.spect = spect
        self.nfft = nfft
        self.overlap = overlap
        self.freqCutoffs = freq_cutoffs
        self.freqBins = freq_bins
        self.timeBins = time_bins
        self.index = index
        self.label = label


class Song:
    """Song object
    used for feature extraction
    """

    def __init__(self,
                 filename,
                 file_format,
                 segment_params=None,
                 use_annotation=True,
                 annote_filename=None,
                 spect_params=None):
        """__init__ function for song object

        either loads annotations, or segments song to find annotations.
        Annotations are:
            onsets_s : 1-d array
            offsets_s : 1-d array, same length as onsets_s
                onsets and offsets of segments in seconds
            onsets_Hz : 1-d array, same length as onsets_s
            offsets_Hz : 1-d array, same length as onsets_s
                onsets and offsets of segments in Hertz
                for isolating segments from raw audio instead of from spectrogram
            labels: 1-d array, same length as onsets_s

        Parameters
        ----------
        filename : str
            name of file
        file_format : str
            {'evtaf','koumura'}
            'evtaf' -- files obtained with EvTAF program [1]_, extension is '.cbin'
            'koumura' -- .wav files from repository [2]_ that accompanied paper [3]_.
        segment_params : dict
            required for any data set that includes segmenting parameters.
            If use_annotation is True, checks values in this dict against
            the parameters in the annotation file (if they are present, not all
            data sets include segmentation parameters).
            Default is None.
            segment_params dict has the following keys:
                threshold : int
                    value above which amplitude is considered part of a segment. default is 5000.
                min_syl_dur : float
                    minimum duration of a segment. default is 0.02, i.e. 20 ms.
                min_silent_dur : float
                    minimum duration of silent gap between segment. default is 0.002, i.e. 2 ms.
        use_annotation : bool
            if True, loads annotations from file.
            default is True.
            if False, segment song during init using spect_params and segment_params.
            if annotation file not found, raises FileNotFound error.
        annote_filename : str
            name of file that contains annotations to use for segments
            default is None.
            If None, __init__ tries to find file automatically
        spect_params : dict
            not required unless use_annotation is False
            keys should be parameters for Spectrogram.__init__,
            see the docstring for those keys.
        """

        if use_annotation is False and segment_params is None:
            raise ValueError('use_annotation set to False but no segment_params '
                             'was provided; segment_params are required to '
                             'find segments.')

        if use_annotation is False and spect_params is None:
            raise ValueError('use_annotation set to False but no spect_params '
                             'was provided; spect_params are required to '
                             'find segments.')

        self.filename = filename
        self.fileFormat = file_format

        if file_format == 'evtaf':
            raw_audio, samp_freq = evfuncs.load_cbin(filename)
        elif file_format == 'koumura':
            samp_freq, raw_audio = wavfile.read(filename)

        self.rawAudio = raw_audio
        self.sampFreq = samp_freq

        if use_annotation:
            if file_format == 'evtaf':
                if segment_params is None:
                    ValueError('segment_params required when '
                               'use_annotation is true for '
                               'evtaf file format')
                if annote_filename:
                    song_dict = evfuncs.load_notmat(annote_filename)
                else:
                    try:
                        song_dict = evfuncs.load_notmat(filename)
                    except FileNotFoundError:
                        print("Could not automatically find an annotation file for {}."
                              .format(filename))
                        raise  # (re-raise FileNotFound that we just caught with except)
                # in .not.mat files saved by evsonganaly,
                # onsets and offsets are in units of ms, have to convert to s
                if segment_params['threshold'] != song_dict['threshold']:
                    raise ValueError('\'threshold\' parameter for {} does not match parameter '
                                     'value for segment_params[\'threshold\'].'
                                     .format(filename))
                if segment_params['min_syl_dur'] != song_dict['min_dur']/1000:
                    raise ValueError('\'min_dur\' parameter for {} does not match parameter '
                                     'value for segment_params[\'min_syl_dur\'].'
                                     .format(filename))
                if segment_params['min_silent_dur'] != song_dict['min_int']/1000:
                    raise ValueError('\'min_int\' parameter for {} does not match parameter '
                                     'value for segment_params[\'min_silent_dur\'].'
                                     .format(filename))
                self.onsets_s = song_dict['onsets'] / 1000
                self.offsets_s = song_dict['offsets'] / 1000
                # subtract one because of Python's zero indexing (first sample is sample zero)
                self.onsets_Hz = np.round(self.onsets_s * self.sampFreq).astype(int) - 1
                self.offsets_Hz = np.round(self.offsets_s * self.sampFreq).astype(int)
            elif file_format == 'koumura':
                if annote_filename:
                    song_dict = koumura.load_song_annot(annote_filename)
                else:
                    try:
                        song_dict = koumura.load_song_annot(filename)
                    except FileNotFoundError:
                        print("Could not automatically find an annotation file for {}."
                              .format(filename))
                        raise
                self.onsets_Hz = song_dict['onsets']  # in Koumura annotation.xml files, onsets given in Hz
                self.offsets_Hz = song_dict['offsets']  # and offsets
                self.onsets_s = self.onsets_Hz / self.sampFreq  # so need to convert to seconds
                self.offsets_s = song_dict['offsets'] / self.sampFreq

            self.labels = song_dict['labels']

        else:  # if use_annotation is False, segment song
            self.spectParams = spect_params
            self.segmentParams = segment_params

            spect_maker = Spectrogram(**spect_params)
            spect, freq_bins, time_bins = spect_maker.make(self.rawAudio,
                                                           self.sampFreq)
            # redundant that I make spect but then throw it away after finding
            # onsets + offsets. Could just keep segment spectrograms but for
            # 'syls_to_use' not being set. Possibly could just assume that
            # 'syls_to_use' == 'all' for unlabeled song
            # Is there any time that would be unwanted behavior?
            amp = compute_amp(spect)
            onsets, offsets = segment_song(amp,
                                           time_bins,
                                           segment_params)
            self.onsets_s = onsets
            self.offsets_s = offsets
            self.onsets_Hz = np.round(self.onsets_s * self.sampFreq).astype(int)
            self.offsets_Hz = np.round(self.offsets_s * self.sampFreq).astype(int)
            self.labels = '-' * len(onsets)

    def set_syls_to_use(self, labels_to_use='all'):
        """        
        Parameters
        ----------
        labels_to_use : list or string
            List or string of all labels for which associated spectrogram should be made.
            When called by extract, this function takes a list created by the
            extract config parser. But a user can call the function with a string.
            E.g., if labels_to_use = 'iab' then syllables labeled 'i','a',or 'b'
            will be extracted and returned, but a syllable labeled 'x' would be
            ignored. If labels_to_use=='all' then all spectrograms are returned with
            empty strings for the labels. Default is 'all'.
        
        sets syls_to_use to a numpy boolean that can be used to index e.g. labels, onsets
        This method must be called before get_syls
        """

        if labels_to_use != 'all':
            if type(labels_to_use) != list and type(labels_to_use) != str:
                raise ValueError('labels_to_use argument should be a list or string')
            if type(labels_to_use) == str:
                labels_to_use = list(labels_to_use)

        if labels_to_use == 'all':
            self.syls_to_use = np.ones((self.onsets_s.shape),dtype=bool)
        else:
            self.syls_to_use = np.in1d(list(self.labels),
                                       labels_to_use)

    def make_syl_spects(self,
                        spect_params,
                        syl_spect_width=-1,
                        set_syl_spects=True,
                        return_spects=False):
        """Make spectrograms from syllables.
        This method isolates making spectrograms from selecting syllables
        to use so that spectrograms can be loaded 'lazily', e.g., if only
        duration features are being extracted that don't require spectrograms.

        Parameters
        ----------

        spect_params : dict
            keys should be parameters for Spectrogram.__init__,
            see the docstring for those keys.
        syl_spect_width : int
            Optional parameter to set constant duration for each spectrogram of a
            syllable, in seconds. E.g., 0.05 for an average 50 millisecond syllable. 
            Used for creating inputs to neural network where each input
            must be of a fixed size.
            Default value is -1; in this case, the width of the spectrogram will
            be the duration of the syllable as determined by the segmentation
            algorithm, i.e. the onset and offset that are stored in an annotation file.
            If a different value is given, then the duration of each spectrogram
            will be that value. Note that if any individual syllable has a duration
            greater than syl_spect_duration, the function raises an error.
        set_syl_spects : bool
            if True, creates syllable objects for each segment in song,
             as defined by onsets and offsets,
             and assigns to each syllable's `spect` property the
            spectrogram of that segment.
            Default is True.
        return_spects : bool
            if True, return spectrograms.
            Can be used without affecting syllables that have already been set
            for a song.
            Default is False.
        """

        if not hasattr(self, 'syls_to_use'):
            raise ValueError('Must set syls_to_use by calling set_syls_to_use method '
                             'before calling get_syls.')

        if not hasattr(self, 'raw_audio') and not hasattr(self, 'sampFreq'):
            if self.fileFormat == 'evtaf':
                    raw_audio, samp_freq = evfuncs.load_cbin(self.filename)
            elif self.fileFormat == 'koumura':
                samp_freq, raw_audio = wavfile.read(self.filename)
            self.rawAudio = raw_audio
            self.sampFreq = samp_freq

        if syl_spect_width > 0:
            if syl_spect_width > 1:
                warnings.warn('syl_spect_width set greater than 1; note that '
                              'this parameter is in units of seconds, so using '
                              'a value greater than one will make it hard to '
                              'center the syllable/segment of interest within'
                              'the spectrogram, and additionally consume a lot '
                              'of memory.')
            syl_spect_width_Hz = int(syl_spect_width * self.sampFreq)
            if syl_spect_width_Hz > self.rawAudio.shape[-1]:
                raise ValueError('syl_spect_width, converted to samples, '
                                 'is longer than song file {}.'
                                 .format(self.filename))

        all_syls = []

        spect_maker = Spectrogram(**spect_params)

        for ind, (label, onset, offset) in enumerate(zip(self.labels, self.onsets_Hz, self.offsets_Hz)):
            if 'syl_spect_width_Hz' in locals():
                syl_duration_in_samples = offset - onset
                if syl_duration_in_samples > syl_spect_width_Hz:
                    raise ValueError('syllable duration of syllable {} with label {} '
                                     'in file {} is greater than '
                                     'width specified for all syllable spectrograms.'
                                     .format(ind, label, self.filename))

            if self.syls_to_use[ind]:
                if 'syl_spect_width_Hz' in locals():
                    width_diff = syl_spect_width_Hz - syl_duration_in_samples
                    # take half of difference between syllable duration and spect width
                    # so one half of 'empty' area will be on one side of spect
                    # and the other half will be on other side
                    # i.e., center the spectrogram
                    left_width = int(round(width_diff / 2))
                    right_width = width_diff - left_width
                    if left_width > onset:  # if duration before onset is less than left_width
                        # (could happen with first onset)
                        left_width = 0
                        right_width = width_diff - offset
                    elif offset + right_width > self.rawAudio.shape[-1]:
                        # if right width greater than length of file
                        right_width = self.rawAudio.shape[-1] - offset
                        left_width = width_diff - right_width
                    syl_audio = self.rawAudio[onset - left_width:offset + right_width]
                else:
                    syl_audio = self.rawAudio[onset:offset]

                try:
                    spect, freq_bins, time_bins = spect_maker.make(syl_audio,
                                                                   self.sampFreq)
                except WindowError as err:
                    warnings.warn('Segment {0} in {1} with label {2} '
                                  'not long enough for window function'
                                  ' set with current spect_params.\n'
                                  'spect will be set to nan.'
                                  .format(ind, self.filename, label))
                    spect, freq_bins, time_bins = (np.nan,
                                                   np.nan,
                                                   np.nan)

                curr_syl = syllable(syl_audio,
                                    self.sampFreq,
                                    spect,
                                    spect_maker.nperseg,
                                    spect_maker.noverlap,
                                    spect_maker.freqCutoffs,
                                    freq_bins,
                                    time_bins,
                                    ind,
                                    label)

                all_syls.append(curr_syl)
        if set_syl_spects:
            self.syls = all_syls

        if return_spects:
            return [syl.spect for syl in all_syls]