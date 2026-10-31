import soundfile as sf, glob
print(sf.__libsndfile_version__)
ps = ['/mnt/c/Users/ksysh/Downloads/Norihiro_Tsuru_-_Last_Carnival_Acoustic_Cafe_(mp3.pm).mp3',
      '/mnt/c/Users/ksysh/Desktop/백업/SdCardBackUp/Music/TalesWeaver OST/10. Beyond.flac',
      '/mnt/c/Users/ksysh/Desktop/백업/SdCardBackUp/Music/TalesWeaver OST/31 Beyond (English ver.) (Ending Movie).mp3.flac']
for p in ps:
    try:
        i = sf.info(p); print(i.samplerate, i.channels, i.duration, i.format, i.subtype)
    except Exception as e:
        print('ERR', p, e)
