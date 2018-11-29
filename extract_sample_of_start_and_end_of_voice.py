import collections
import contextlib
import sys
import wave
from wave import Wave_read
import webrtcvad
import glob

#an array that keep end time(ms) of a voice file 
etm = []

#an array that keep start time(ms) of a voice file 
stm = []

def read_wave(path):
    """Reads a .wav file.

    Takes the path, and returns (PCM audio data, sample rate).
    """
    with contextlib.closing(wave.open(path, 'rb')) as wf:
        num_channels = wf.getnchannels()
        assert num_channels == 1
        sample_width = wf.getsampwidth()
        assert sample_width == 2
        sample_rate = wf.getframerate()
        assert sample_rate in (8000, 16000, 32000)
        pcm_data = wf.readframes(wf.getnframes())
        return pcm_data, sample_rate


def write_wave(path, audio, sample_rate):
    """Writes a .wav file.

    Takes path, PCM audio data, and sample rate.
    """
    with contextlib.closing(wave.open(path, 'wb')) as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio)


class Frame(object):
    """Represents a "frame" of audio data."""
    def __init__(self, bytes, timestamp, duration):
        self.bytes = bytes
        self.timestamp = timestamp
        self.duration = duration


def frame_generator(frame_duration_ms, audio, sample_rate):
    """Generates audio frames from PCM audio data.

    Takes the desired frame duration in milliseconds, the PCM data, and
    the sample rate.

    Yields Frames of the requested duration.
    """
    n = int(sample_rate * (frame_duration_ms / 1000.0) * 2)
    offset = 0
    timestamp = 0.0
    duration = (float(n) / sample_rate) / 2.0
    while offset + n < len(audio):
        yield Frame(audio[offset:offset + n], timestamp, duration)
        timestamp += duration
        offset += n

def vad_collector(sample_rate, frame_duration_ms,
                  padding_duration_ms, vad, frames):
    """Filters out non-voiced audio frames.

    Given a webrtcvad.Vad and a source of audio frames, yields only
    the voiced audio.

    Uses a padded, sliding window algorithm over the audio frames.
    When more than 90% of the frames in the window are voiced (as
    reported by the VAD), the collector triggers and begins yielding
    audio frames. Then the collector waits until 90% of the frames in
    the window are unvoiced to detrigger.

    The window is padded at the front and back to provide a small
    amount of silence or the beginnings/endings of speech around the
    voiced frames.

    Arguments:

    sample_rate - The audio sample rate, in Hz.
    frame_duration_ms - The frame duration in milliseconds.
    padding_duration_ms - The amount to pad the window, in milliseconds.
    vad - An instance of webrtcvad.Vad.
    frames - a source of audio frames (sequence or generator).

    Returns: A generator that yields PCM audio data.
    """
    num_padding_frames = int(padding_duration_ms / frame_duration_ms)
    # We use a deque for our sliding window/ring buffer.
    ring_buffer = collections.deque(maxlen=num_padding_frames)

    # We have two states: TRIGGERED and NOTTRIGGERED. We start in the
    # NOTTRIGGERED state.
    triggered = False

    voiced_frames = []
    # start_frame = 0

    for frame in frames:
        is_speech = vad.is_speech(frame.bytes, sample_rate)
        sys.stdout.write('1' if is_speech else '0')
        if not triggered:
            ring_buffer.append((frame, is_speech))
            num_voiced = len([f for f, speech in ring_buffer if speech])
            # If we're NOTTRIGGERED and more than 90% of the frames in
            # the ring buffer are voiced frames, then enter the
            # TRIGGERED state.
            if num_voiced > 0.9 * ring_buffer.maxlen:
                triggered = True
                sys.stdout.write('+(%s)' % (ring_buffer[0][0].timestamp,))

                #each time that reconize frame is a voice from append time in stm
                    #but maybe this frame is a noise frame then always in the last position in stm
                    #saved corrent start time
                stm.append(ring_buffer[0][0].timestamp)
                # We want to yield all the audio we see from now until
                # we are NOTTRIGGERED, but we have to start with the
                # audio that's already in the ring buffer.
                
                for f, s in ring_buffer:
                    voiced_frames.append(f)
                ring_buffer.clear()
        else:
            # We're in the TRIGGERED state, so collect the audio data
            # and add it to the ring buffer.
            voiced_frames.append(frame)
            ring_buffer.append((frame, is_speech))
            num_unvoiced = len([f for f, speech in ring_buffer if not speech])
            # If more than 90% of the frames in the ring buffer are
            # unvoiced, then enter NOTTRIGGERED and yield whatever
            # audio we've collected.
            if num_unvoiced > 0.9 * ring_buffer.maxlen:
                sys.stdout.write(' -(%s)' % (frame.timestamp + frame.duration))
                
                #each time that reconize frame is end of  speech  append time in etm
                    #but maybe this frame is a noise frame then always in the last position in etm
                    #saved corrent end time
                etm.append(frame.timestamp + frame.duration)
                triggered = False
                yield b''.join([f.bytes for f in voiced_frames])
                ring_buffer.clear()
                voiced_frames = []

    #if tell us if in the first time we have a voice frame then must save this time 
    if triggered:
        sys.stdout.write(' -(%s)' % (frame.timestamp + frame.duration))
        etm.append(frame.timestamp + frame.duration)
    sys.stdout.write('\n')
    # If we have any leftover voiced audio when we run out of input,
    # yield it.
    if voiced_frames:
        yield b''.join([f.bytes for f in voiced_frames])
   

def main(args):

    #information of voice file (include: file name + start sapmple of speech+ end sapmle of speech + end sample of file) that write in the dataset.txt
    info = []

    #direction input address
    dir_files = glob.glob("*.wav")

    #sort input(not necessary)
    dir_files.sort()

    #an array that keep end of sample of file
    end_sample_file = []

    #start sample of speech
    start_sample_speech = []

    #end sample of speech
    end_sample_speech = []

    #name of orfinal file that cut postfix(not ncessary)
    fileName = []

    #start time(ms) of speech in voice files
    st = []

   #end time(ms) of speech in voice files
    et = []

    #sample rate of all voice file
    sample_rates = []
    #counter in the loop
    count = 0
    #loop in directory
    for n in dir_files:
        #open voice file 
        vc=wave.open(n)

        #append end sample of file in the array
        end_sample_file.append(Wave_read.getnframes(vc))

        #append sample rate of voice file in the aray
        sample_rates.append(Wave_read.getframerate(vc))

        #read_wave is a function that get voice file directory and return audio(in spation format)
        audio, sample_rate = read_wave(n)

        #this is a function of webrtcvad that get a parameter (integer between 0,3) that defind Accurancy
        vad = webrtcvad.Vad(3)
        #generate fram (first parameter is size of window )
        frames = frame_generator(10, audio, sample_rate)
        frames = list(frames)

        #this is main function that recognize speech in the voice file
        segments = vad_collector(sample_rate, 30, 300, vad, frames)
        
        #this for create a voice file that cut unvoiced part of orginal voice file and saved in a new file
        for i, segment in enumerate(segments):
            path = 'edited_'+n
            write_wave(path, segment, sample_rate)

        #split name of filefrom postfix of orginal file (not necessary)
        temp_str=n.split('.')
        fileName.append(temp_str[0])

        #start time(ms) of speech in the voice file
        st.append(stm[-1])
        print('start time (ms) of speech ',n,' is',st[-1])
        #start time(ms) of speech in the voice file
        et.append(etm[-1])
        print('end time (ms) of speech ',n,' is',et[-1])

        #note!
            #stm and etm that use in the vad_collector function are start time and end time of 
                #voice file but because of noise in file maybe those variable get noise time  
                #instead of speech time but in the last position in the array always has a speech
                #time . more information in the vad_collector function
        count = count+1

    #convert all start time of speech in time to sample and saved in satart_samle
    for i in range(0,len(st)):
        start_sample_speech.append(st[i]*sample_rates[i])

    #convert all end time of speech in time to sample and saved in end_samle
    for i in range(0,len(et)):
        end_sample_speech.append(et[i]*sample_rates[i])

    #fill informatio of voice file
    for i in range(0,len(fileName)):
        info.append(fileName[i]+' '+str(int(start_sample_speech[i]))+' '+str(int(end_sample_speech[i]))+' '+str(end_sample_file[i]))

    #write info in the file
    f = open('dataset.txt','w')
    for n in info:
        f.write(n+'\n')
    f.close()



if __name__ == '__main__':
    main(sys.argv[1:])
