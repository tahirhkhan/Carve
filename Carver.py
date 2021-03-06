#TODO Verify b'' not '' for all searches
#TODO Verify that I am incrementing sectors, not bytes
#TODO Find out how to search backwards and what ends.
#0e63e6cc0426d87fd30d597a0a572a27,2d70374751335bcea8b6e3a8ced85a5fd2fe142e,png
#34e4a705ab20b8c39b053cdd0d2e145e,f3ce8b3ead5836d054da50b149e83ea17ca1d4ee,jpg
#2eeb5d2e239f35faa98b7ad119f4620c,ecb8ed802f44962c996a0888c03946d94141f7fa,gif
#54c04b301ee28028369aaad0fa4ec1e7,38cdd190dedd25923a95b53a90f0270f1de8c463,bmp
import sys
import argparse
import datetime
import signal
import struct
import hashlib
import os.path
from sys import platform as _platform

debug = 0
#References Microsoft's FAT General Overview 1.03
# <editor-fold desc="Boot Sector Variables">

BytesPerSector = ''  #Offset 11 - 2 bytes
SectorsPerCluster = ''  #Offset 13 - 1 byte
ReservedSectorCount = ''  #Offset 14 - 2 bytes
NumberOfFATs = ''  #Offset 16 - 1 byte
TotalSectors = ''  #Offset 32 - 4 bytes
# Start of FAT32 Structure 
FAT32Size = ''  #Offset 36 - 4 bytes
RootCluster = ''  #Offset 44 - 4 bytes
FSInfoSector = ''  #Offset 48 - 2 bytes
ClusterSize = ''
TotalFAT32Sectors = ''
TotalFAT32Bytes = ''
DataAreaStart = ''
DataAreaEnd = ''
RootDirSectors = 0  #Always 0 for Fat32 Per MS Documentation
#FSINFO 
Signature = ''
NumberOfFreeClusters = 0
NextFreeCluster = 0
BootSectorSize = 512
# </editor-fold>

# <editor-fold desc="Global Variables">

ValidBytesPerSector = [512, 1024, 2048, 4096]

GIFHeadChunk = []
GIFFootChunk = []
GIFData = []
PNGHeadChunk = []
PNGFootChunk = []
PNGData = []
BMPData = []
JPGHeadChunk = []
JPGFootChunk = []
JPGData = []
JPGFootStart = 0
JPGFootEnd = 0
PNGFootStart = 0
PNGFootEnd = 0
GIFFootEnd = 0
GIFFootStart = 0
KnownOffsets = []
gifs = []
jpgs = []
pngs = []
bmps = []
maximum = 10000000
MaximumBMPSize = 10000000
MaximumJPGSize = 10000000
MaximumGIFSize = 10000000
MaximumPNGPSize = 10000000
usedsectors = []

# </editor-fold>


class NotValidBootSector(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)



def IdentifyFileSystem(volume):
    status = True
    error = ''
    bootsector = True
    global BootSectorSize
    global ValidBytesPerSector

    try:
        if debug >= 1:
            print('Entering IdentifyFileSystem:')
        with open(volume, "rb") as f:
            byte = f.read(BootSectorSize)
            BytesPerSector = struct.unpack("<H", byte[11:13])[0]
            if BytesPerSector not in ValidBytesPerSector:
                #raise NotValidBootSector('Only FAT32 supported.')
                BytesPerSector = 512
                bootsector = False

    except:
        status = False
        error = 'Cannot read Boot Sector.'
    finally:
        return status, error, bootsector


def ReadBootSector(volume):
    # <editor-fold desc="Global Variables">
    global DataAreaStart
    global BytesPerSector
    global SectorsPerCluster
    global ReservedSectorCount
    global NumberOfFATs
    global TotalSectors
    # Start of FAT32 Structure
    global FAT32Size
    global RootCluster
    global FSInfoSector
    global ClusterSize
    global TotalFAT32Sectors
    global TotalFAT32Bytes
    global DataAreaStart
    global DataAreaEnd
    global FirstDataSector
    # </editor-fold>
    nobootsector = False
    status = True
    error = ''

    # Reads the specified bytes from the drive
    try:
        if debug >= 1:
            print('Entering ReadBootSector:')
        with open(volume, "rb") as f:
            byte = f.read(BootSectorSize)
            BytesPerSector = struct.unpack("<H", byte[11:13])[0]
            if BytesPerSector not in ValidBytesPerSector:
                BytesPerSector = 512
                nobootsector = True
            SectorsPerCluster = struct.unpack("<b", byte[13:14])[0]
            ReservedSectorCount = struct.unpack("<H", byte[14:16])[0]
            NumberOfFATs = struct.unpack("<b", byte[16:17])[0]
            TotalSectors = struct.unpack("i", byte[32:36])[0]
            FAT32Size = struct.unpack("i", byte[36:40])[0]
            RootCluster = struct.unpack("i", byte[44:48])[0]
            FSInfoSector = struct.unpack("<H", byte[48:50])[0]

            #Calculate some values
            ClusterSize = SectorsPerCluster * BytesPerSector
            TotalFAT32Sectors = FAT32Size * NumberOfFATs
            TotalFAT32Bytes = FAT32Size * BytesPerSector

            DataAreaStart = ReservedSectorCount + TotalFAT32Sectors
            DataAreaEnd = TotalSectors - 1  #Base 0
            if not nobootsector:
                FirstDataSector = ReservedSectorCount + (NumberOfFATs * FAT32Size) + RootDirSectors
                if debug >= 2:
                    print('\tFirstDataSector = ' + str(FirstDataSector))
            else:
                FirstDataSector = 0
                if debug >= 2:
                    print('\tFirstDataSector = ' + str(FirstDataSector))
            if not nobootsector:
                if debug >= 1:
                    print('\tBytes per Sector: ' + str(BytesPerSector))
                    print('\tSectors per Cluster: ' + str(SectorsPerCluster))
                    print('\tCluster Size: ' + str(ClusterSize))
                    print('\tRoot Cluster: ' + str(RootCluster))
                    print('\tFSInfo Cluster: ' + str(FSInfoSector))
                    print('\tTotal Sectors: ' + str(TotalSectors))
                    print('\tReserved Sector Count: ' + str(ReservedSectorCount))
                    print('\tReserved Sectors: ' + '0  - ' + str(ReservedSectorCount - 1))
                    print('\tFAT Offset: ' + str(ReservedSectorCount))
                    print('\tFAT Offset (Bytes): ' + str(ReservedSectorCount * BytesPerSector))
                    print('\tNumber of FATs: ' + str(NumberOfFATs))
                    print('\tFAT32 Size: ' + str(FAT32Size))
                    print('\tTotal FAT32 Sectors: ' + str(TotalFAT32Sectors))
                    print('\tFAT Sectors: ' + str(ReservedSectorCount) + ' - ' + str(
                        (ReservedSectorCount - 1) + (FAT32Size * NumberOfFATs)))
                    print('\tData Area: ' + str(DataAreaStart) + ' - ' + str(DataAreaEnd))
                    print('\tData Area Offset (Bytes): ' + str(DataAreaStart * BytesPerSector))
                    #print('\tRoot Directory: ' + str(DataAreaStart) + ' - ' + str(DataAreaStart + 3))
                    #Extra Testing
                    print('\t   First Data Sector: ' + str(FirstDataSector))
    except IOError:
        status = False
        error = 'Volume ' + str(volume) + ' does not exist.'
    except:
        status = False
        error = 'Cannot read Boot Sector.'
    finally:
        return status, error


def WriteDatatoFile(path):
    status = True
    error = ''
    global jpgs
    global pngs
    global gifs
    global bmps
    ba = b''
    path += '\\'

    try:
        if debug >= 1:
            print('Entering WriteDatatoFile:')
        if debug >= 2:
            print('\tPath entered: ' + str(path))
        if gifs:
            for g in gifs:
                for b in g:
                    ba += b
                if debug >= 3:
                    print('\tRaw byte data: ' + str(ba))
                with open(path + str(Hasher(g, 'md5') + '.gif'), "wb") as f:
                    f.write(ba)
        else:
            if debug >= 2:
                print('\tNo GIF Data found.')

        if pngs:
            for png in pngs:
                ba = b''
                for b in png:
                    ba += b
                if debug >= 3:
                    print('\tRaw byte data: ' + str(ba))
                with open(path + str(Hasher(png, 'md5') + '.png'), "wb") as f:
                    f.write(ba)
        else:
            if debug >= 2:
                print('\tNo PNG Data found.')

        if jpgs:
            for jpg in jpgs:
                ba = b''
                for b in jpg:
                    ba += b
                if debug >= 3:
                    print('\tRaw byte data: ' + str(ba))
                with open(path + str(Hasher(jpg, 'md5') + '.jpg'), "wb") as f:
                    f.write(ba)
        else:
            if debug >= 2:
                print('\tNo JPG Data found.')

        if bmps:
            for bmp in bmps:
                ba = b''
                for b in bmp:
                    ba += b
                if debug >= 3:
                    print('\tRaw byte data: ' + str(ba))
                with open(path + str(Hasher(bmp, 'md5') + '.bmp'), "wb") as f:
                    f.write(ba)
        else:
            if debug >= 2:
                print('\tNo BMP Data found.')
    except:
        error = 'Error: Cannot Write Data.'
        status = False
    finally:
        return status, error


def SearchGIFs(volume):
    status = True
    error = ''
    counter = 0
    slider = 0
    byte = b''
    data = []
    global gifs
    endofgif = False
    backwards = 0
    GIFFootChunk = []
    GIFData = []
    GIFEnd = []
    GIFFootEnd = 0
    offsetfromsector = 0
    breaker = False


    try:
        if debug >= 1:
            print('Entering SearchGIFs')
        if debug >= 2:
            print('\tVolume Passed in: ' + str(volume))
        with open(volume, "rb") as f:
            if debug >= 2:
                print('\tSeeking to First Data Sector [Bytes]: ' + str(BytesPerSector * FirstDataSector))
            f.seek(BytesPerSector * FirstDataSector)
            sector = f.read(BytesPerSector)
            while sector != b'':
                #Identify GIF Header
                if sector[0:6] == b'GIF89a' or sector[0:6] == b'GIF87a':
                    if debug >= 2:
                        print('\tGIF Header found at offset [Bytes]: ' + str((BytesPerSector * FirstDataSector) + counter))
                    data.append(sector)
                    while byte != b'\x3b\x00\x00\x00':
                        endofgif = False
                        sector = f.read(BytesPerSector)
                        counter += BytesPerSector
                        if sector == b'':
                            break
                        #if sector == 512 * b'\x00':
                        #    continue
                        slider = 0
                        if (sector[0:6] == b'GIF89a') or sector[0:6] == b'GIF87a' or (
                            struct.unpack(">H", sector[0:2])[0] == 0xFFD8) or (
                            struct.unpack(">H", sector[0:2])[0] == 0x424D) or (struct.unpack(">Q", sector[0:8])[0] == 0x89504E470D0A1A0A):
                            endofgif = False
                            if debug >= 2:
                                print('\tAlternate header found at offset ' + str((BytesPerSector * FirstDataSector) + counter) + ' Setting flag for 2nd piece search.')
                            if debug >= 3:
                                print('\tMD5 Hash of First Chunk: ' + str(Hasher(data, 'md5')))
                            if debug >= 2:
                                print('\tSearching backwards for GIF End.')
                            #counter = 0

                            breaker = False
                            byte = b'\x00'
                            #f.seek((BytesPerSector * FirstDataSector) + counter)
                            sector = f.read(BytesPerSector)
                            counter += BytesPerSector
                            while sector != b'':
                                if debug >= 3:
                                    print('\tEntering Slider for GIF.')
                                x = BytesPerSector
                                if (struct.unpack(">Q", sector[0:8])[0] != 0x89504E470D0A1A0A) and (
                                            struct.unpack(">H", sector[0:2])[0] != 0xFFD8) and (
                                            struct.unpack(">H", sector[0:2])[0] != 0x424D) and (sector[0:6] != b'GIF89a') and (sector[0:6] != b'GIF87a'):
                                    while x != 0:
                                        if debug >= 3:
                                            print('\tSearching for GIF Footer.')
                                        if sector[BytesPerSector - 1:BytesPerSector] == b'\x00':
                                            firstchars = sector[x - 2:x]
                                            if firstchars == b'\x3b\x00':
                                                if debug >= 2:
                                                    print('\tGIF Footer found.')
                                                GIFFootEnd = (BytesPerSector * FirstDataSector + counter + x - 1)
                                                offsetfromsector = (x - 1)
                                                if debug >= 2:
                                                    print('\tGIF Footer end located at offset [Bytes]: ' + str(GIFFootEnd))
                                                    print('\tOffset from previous sector [Bytes]: ' + str(offsetfromsector))
                                                breaker = True
                                                break
                                            else:
                                                x -= 1
                                        else:
                                            if debug >= 3:
                                                print('\tLast byte not \\x00.')
                                            break
                                    if breaker:
                                        break
                                    counter += BytesPerSector
                                    sector = f.read(BytesPerSector)
                                    if sector == b'':
                                        break
                                    if debug >= 3:
                                        print('\tNext sector: ' + str(BytesPerSector * FirstDataSector + counter))
                                else:
                                    counter += BytesPerSector
                                    sector = f.read(BytesPerSector)
                                    if sector == b'':
                                        break
                                    if debug >= 3:
                                        print('\tNext sector: ' + str(BytesPerSector * FirstDataSector + counter))
                            while True:
                                f.seek(GIFFootEnd - offsetfromsector - backwards - 16)
                                byte = f.read(16)
                                if byte != b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00':
                                    backwards += BytesPerSector
                                else:
                                    GIFFootStart = GIFFootEnd - offsetfromsector - backwards
                                    if debug >= 2:
                                        print('\tGIF Footer start located at offset [Bytes]: ' + str(GIFFootStart))
                                    break
                            f.seek(GIFFootStart)
                            if debug >= 2:
                                print('\tSeeking to Data Sector [Bytes]: ' + str(GIFFootStart))

                            GIFFootChunk.append(f.read(GIFFootEnd - GIFFootStart))
                            GIFData = data + GIFFootChunk
                            gifs.append(GIFData)

                            endofgif = True
                            if debug >= 2:
                                print('\tGIF MD5 Hash: ' + str(Hasher(GIFData, 'md5')))
                            if debug >= 3:
                                print('\tGIF First Chunk: ' + str(data))
                                print('\tGIF Last Chunk: ' + str(GIFFootChunk))
                                print('\tGIF Chunk: ' + str(GIFData))
                            GIFData = []
                            break
                        else:
                            while slider != BytesPerSector:
                                if debug >= 3:
                                    print('\tSearching for GIF end.')
                                byte = sector[slider:slider + 4]
                                if byte == b'\x3b\x00\x00\x00':
                                    if debug >= 3:
                                        print('\tGIF byte and offset: ' + str(
                                            (BytesPerSector * FirstDataSector) + counter + slider) + ' : ' + str(byte))
                                    data.append(sector[0:slider + 1])
                                    gifs.append(data)
                                    if debug >= 2:
                                        print('\tGIF Hash: ' + str(Hasher(data, 'md5')))
                                    endofgif = True
                                    data = []
                                    break
                                else:
                                    slider += 1
                        if not endofgif:
                            data.append(sector)
                else:
                    if debug >= 3:
                        print('\tSector offset [Bytes]: ' + str(BytesPerSector * FirstDataSector + counter))
                        print('\tSector Data: ' + str(sector))
                    byte = b''
                    sector = f.read(BytesPerSector)
                    counter += BytesPerSector
    except:
        error = 'Error: Cannot Find Valid Headers.'
        status = False
    finally:
        return status, error


def SearchPNGs(volume):
    status = True
    error = ''
    counter = 0
    slider = 0
    byte = b''
    data = []
    global pngs
    endofpng = False
    backwards = 0
    PNGFootChunk = []
    PNGData = []
    PNGEnd = []
    PNGFootEnd = 0
    offsetfromsector = 0
    breaker = False

    try:
        if debug >= 1:
            print('Entering SearchPNGs')
        if debug >= 2:
            print('\tVolume Passed in: ' + str(volume))
        with open(volume, "rb") as f:
            if debug >= 2:
                print('\tSeeking to First Data Sector [Bytes]: ' + str(BytesPerSector * FirstDataSector))
            f.seek(BytesPerSector * FirstDataSector)
            sector = f.read(BytesPerSector)
            while sector != b'':
                if struct.unpack(">Q", sector[0:8])[0] == 0x89504E470D0A1A0A:
                    if debug >= 2:
                        print('\tPNG Header found at offset [Bytes]: ' + str((BytesPerSector * FirstDataSector) + counter))
                        print('\tAppending sector to PNG data array.')
                    data.append(sector)
                    while byte != b'\x49\x45\x4E\x44\xAE\x42\x60\x82':
                        endofpng = False
                        sector = f.read(BytesPerSector)
                        counter += BytesPerSector
                        if sector == b'':
                            break
                        #if sector == 512 * b'\x00':
                        #    continue
                        slider = 0
                        if (sector[0:6] == b'GIF89a') or (sector[0:6] == b'GIF897a') or (
                            struct.unpack(">H", sector[0:2])[0] == 0xFFD8) or (
                            struct.unpack(">H", sector[0:2])[0] == 0x424D) or (struct.unpack(">Q", sector[0:8])[0] == 0x89504E470D0A1A0A):
                            endofpng = False
                            if debug >= 2:
                                print('\tAlternate header found at ' + str((BytesPerSector * FirstDataSector) + counter) + '. Setting flag for 2nd piece search.')
                                print('\tSearching backwards for PNG End.')
                            #counter = 0
                            breaker = False
                            byte = b'\x00'
                            #f.seek(BytesPerSector * FirstDataSector)
                            sector = f.read(BytesPerSector)
                            counter += BytesPerSector
                            while byte != b'':
                                if debug >= 3:
                                    print('\tEntering Slider for PNG.')
                                x = BytesPerSector
                                if (struct.unpack(">Q", sector[0:8])[0] != 0x89504E470D0A1A0A) and (
                                            struct.unpack(">H", sector[0:2])[0] != 0xFFD8) and (
                                            struct.unpack(">H", sector[0:2])[0] != 0x424D) and (sector[0:6] != b'GIF89a') and (sector[0:6] != b'GIF87a'):
                                    while x != 0:
                                        if debug >= 3:
                                            print('\tSearching for PNG Footer.')
                                        if sector[BytesPerSector - 1:BytesPerSector] == b'\x00':
                                            firstchars = sector[x - 8:x]
                                            if firstchars == b'\x49\x45\x4E\x44\xAE\x42\x60\x82':
                                                if debug >= 2:
                                                    print('\tPNG Footer found.')
                                                PNGFootEnd = (BytesPerSector * FirstDataSector + counter + x - 1)
                                                offsetfromsector = (x - 1)
                                                if debug >= 2:
                                                    print('\tPNG Footer end located at offset [Bytes]: ' + str(PNGFootEnd))
                                                    print('\tOffset from previous sector [Bytes]: ' + str(offsetfromsector))
                                                breaker = True
                                                break
                                            else:
                                                x -= 1
                                        else:
                                            if debug >= 3:
                                                print('\tLast byte not \\x00.')
                                            break
                                    if breaker:
                                        break
                                    counter += BytesPerSector
                                    sector = f.read(BytesPerSector)
                                    if sector == b'':
                                        break
                                    if debug >= 3:
                                        print('\tNext sector: ' + str(BytesPerSector * FirstDataSector + counter))
                                else:
                                    counter += BytesPerSector
                                    byte = f.read(BytesPerSector)
                            while True:
                                f.seek(PNGFootEnd - offsetfromsector - backwards - 16)
                                byte = f.read(16)
                                if byte != b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00':
                                    backwards += BytesPerSector
                                else:
                                    PNGFootStart = PNGFootEnd - offsetfromsector - backwards
                                    if debug >= 2:
                                        print('\tPNG Footer start located at offset [Bytes]: ' + str(PNGFootStart))
                                    break
                            f.seek(PNGFootStart)
                            if debug >= 2:
                                print('\tSeeking to Data Sector [Bytes]: ' + str(PNGFootStart))
                            PNGFootChunk.append(f.read(PNGFootEnd + 1 - PNGFootStart))
                            PNGData = data + PNGFootChunk
                            pngs.append(PNGData)
                            endofpng = True
                            if debug >= 2:
                                print('\tPNG MD5 Hash: ' + str(Hasher(PNGData, 'md5')))
                            if debug >= 3:
                                print('\tPNG First Chunk: ' + str(data))
                                print('\tPNG Last Chunk: ' + str(PNGFootChunk))
                                print('\tPNG Chunk: ' + str(PNGData))
                            PNGData = []
                            break
                        else:
                            while slider != BytesPerSector:
                                if debug >= 3:
                                    print('\tSearching for PNG end.')
                                byte = sector[slider:slider + 8]
                                if byte == b'\x49\x45\x4E\x44\xAE\x42\x60\x82':
                                    if debug >= 3:
                                        print('\tPNG Footer bytes and offset: ' + str(
                                            (BytesPerSector * FirstDataSector) + counter + slider) + ' : ' + str(byte))
                                    data.append(sector[0:slider + 8])
                                    pngs.append(data)
                                    if debug >= 2:
                                        print('\tPNG MD5 Hash: ' + str(Hasher(data, 'md5'))) #0e63e6cc0426d87fd30d597a0a572a27
                                    if debug >= 3:
                                        print('\tPNG Data [Length]: ' + '[' + str(len(data)) + '] ' + str(data))   #0e63e6cc0426d87fd30d597a0a572a27
                                    endofpng = True
                                    data = []
                                    break
                                else:
                                    slider += 1
                        if not endofpng:
                            data.append(sector)
                else:
                    if debug >= 3:
                        print('\tSector offset [Bytes]: ' + str(BytesPerSector * FirstDataSector + counter))
                        print('\tSector Data: ' + str(sector))
                    byte = b''
                    sector = f.read(BytesPerSector)
                    counter += BytesPerSector
    except:
        error = 'Error: Cannot Find Valid Headers.'
        status = False
    finally:
        return status, error


def SearchBMPs(volume):
    status = True
    error = ''
    global BytesPerSector
    global FirstDataSector
    global BMPData
    global bmps
    global MaximumBMPSize
    endofbmp = False
    counter = 0

    try:
        if debug >= 1:
            print('Entering SearchBMPs:')
        if debug >= 2:
            print('\tVolume Passed in: ' + str(volume))
        with open(volume, "rb") as f:
            if debug >= 2:
                print('\tSeeking to First Data Sector [Bytes]: ' + str(BytesPerSector * FirstDataSector))
            f.seek(BytesPerSector * FirstDataSector)
            sector = f.read(BytesPerSector)

            while sector != b'':
                if struct.unpack(">H", sector[0:2])[0] == 0x424D:
                    BMPFilesize = struct.unpack("<I", sector[2:6])[0]
                    if debug >= 2:
                        print('\tBMP Header found at offset: ' + str((BytesPerSector * FirstDataSector) + counter))
                        print('\tBMP Filesize: ' + str(BMPFilesize))
                    if BMPFilesize >= MaximumBMPSize:
                        if debug >= 2:
                            print('\tBMP Filesize greater than Max (10MB): ' + str(BMPFilesize))
                        sector = f.read(BytesPerSector)
                        counter += BytesPerSector
                        continue

                    BMPData.append(sector)
                    bytestoread = BMPFilesize - BytesPerSector
                    while True:
                        sector = f.read(BytesPerSector)
                        if sector == b'':
                            break
                        counter += BytesPerSector
                        # if (sector[0:6] == b'GIF89a') or (
                        #     struct.unpack(">H", sector[0:2])[0] == 0xFFD8) or (
                        #     struct.unpack(">H", sector[0:2])[0] == 0x424D) or (struct.unpack(">Q", sector[0:8])[0] == 0x89504E470D0A1A0A):
                        #     if debug >= 2:
                        #         print('\tAlternate BMP header found at ' + str((BytesPerSector * FirstDataSector) + counter) + '. Setting flag for 2nd piece search.')
                        #     endofbmp = False
                        #     break
                        # else:
                        if bytestoread > BytesPerSector:
                            BMPData.append(sector)
                            bytestoread -= BytesPerSector
                        else:
                            BMPData.append(sector[0:bytestoread])
                            bytestoread -= bytestoread
                            endofbmp = True
                            bmps.append(BMPData)

                            if debug >= 2:
                                print('\tBMP MD5 Hash: ' + Hasher(BMPData, 'md5'))
                            if debug >= 3:
                                print('\tBMP Data: ' + str(BMPData))
                                print('\tBytes left: ' + str(bytestoread))
                            BMPData = []
                            break

                else:
                    sector = f.read(BytesPerSector)
                    counter += BytesPerSector
    except:
        error = 'Error: Cannot Find BMP Valid Headers.'
        status = False
    finally:
        return status, error


def SearchJPGs(volume):
    status = True
    error = ''
    counter = 0
    slider = 0
    byte = b''
    data = []
    global jpgs
    endofjpg = False
    backwards = 0
    JPGFootChunk = []
    JPGData = []
    JPGEnd = []
    JPGFootEnd = 0
    offsetfromsector = 0
    breaker = False


    try:
        if debug >= 1:
            print('Entering SearchJPGs')
        if debug >= 2:
            print('\tVolume Passed in: ' + str(volume))
        with open(volume, "rb") as f:
            if debug >= 2:
                print('\tSeeking to First Data Sector [Bytes]: ' + str(BytesPerSector * FirstDataSector))
            f.seek(BytesPerSector * FirstDataSector)
            sector = f.read(BytesPerSector)
            while sector != b'':
                if struct.unpack(">H", sector[0:2])[0] == 0xFFD8:
                    data.append(sector)
                    if debug >= 2:
                        print('\tJPG Header found at offset [Bytes]: ' + str((BytesPerSector * FirstDataSector) + counter))
                        print('\tAppending sector to JPG data array.')

                    while byte != b'\xFF\xD9\x00\x00\x00\x00':
                        endofjpg = False
                        if debug >= 4:
                            print('\tEntering While Loop EOJPG.')
                        if debug >= 4:
                            print('\tBytes not equal to JPG footer.')
                        sector = f.read(BytesPerSector)
                        counter += BytesPerSector
                        if sector == b'':
                            break
                        #if sector == 512 * b'\x00':
                        #    continue
                        slider = 0
                        if (sector[0:6] == b'GIF89a') or (sector[0:6] == b'GIF87a') or (struct.unpack(">H", sector[0:2])[0] == 0x424D) or (struct.unpack(">Q", sector[0:8])[0] == 0x89504E470D0A1A0A) or (struct.unpack(">H", sector[0:2])[0] == 0xFFD8):
                            endofjpg = False
                            if debug >= 2:
                                print('\tAlternate header found at ' + str((BytesPerSector * FirstDataSector) + counter) + '. Setting flag for 2nd piece search.')
                            if debug >= 2:
                                print('\tSearching backwards for JPG End.')
                            #counter = 0
                            breaker = False
                            byte = b'\x00'
                            #f.seek(BytesPerSector * FirstDataSector)  #seeking to root data again to start looking for end of JPG
                            sector = f.read(BytesPerSector)
                            counter += BytesPerSector
                            while sector != b'':
                                if debug >= 3:
                                    print('\tEntering Slider for JPG.')
                                x = BytesPerSector
                                if (struct.unpack(">Q", sector[0:8])[0] != 0x89504E470D0A1A0A) and (
                                            struct.unpack(">H", sector[0:2])[0] != 0xFFD8) and (
                                            struct.unpack(">H", sector[0:2])[0] != 0x424D) and (sector[0:6] != b'GIF89a') and (sector[0:6] != b'GIF87a'):
                                    while x != 0:
                                        if debug >= 3:
                                            print('\tSearching for JPG Footer.')
                                        if sector[BytesPerSector - 1:BytesPerSector] == b'\x00':
                                            if debug >= 3:
                                                print('\tLast byte of sector is \\x00.')
                                            firstchars = sector[x - 4:x]
                                            if firstchars == b'\xFF\xD9\x00\x00':
                                                if debug >= 2:
                                                    print('\tJPG Footer found.')
                                                JPGFootEnd = (BytesPerSector * FirstDataSector + counter + x - 2)
                                                offsetfromsector = (x - 2)
                                                if debug >= 2:
                                                    print('\tJPG Footer end located at offset [Bytes]: ' + str(JPGFootEnd))
                                                    print('\tOffset from previous sector [Bytes]: ' + str(offsetfromsector))
                                                breaker = True
                                                break
                                            else:
                                                x -= 1
                                        else:
                                            if debug >= 3:
                                                print('\tLast byte not \\x00.')
                                            break
                                    if breaker:
                                        break
                                    counter += BytesPerSector
                                    sector = f.read(BytesPerSector)
                                    if sector == b'':
                                        break
                                    if debug >= 3:
                                        print('\tNext sector: ' + str(BytesPerSector * FirstDataSector + counter))
                                else:
                                    sector = f.read(BytesPerSector)
                                    counter += BytesPerSector
                                    if sector == b'':
                                        break
                            while True:
                                f.seek(JPGFootEnd - offsetfromsector - backwards - 16)
                                barray = f.read(16)
                                if barray != b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00':
                                    backwards += BytesPerSector
                                else:
                                    JPGFootStart = JPGFootEnd - offsetfromsector - backwards
                                    if debug >= 2:
                                        print('\tJPG Footer start located at offset [Bytes]: ' + str(JPGFootStart))
                                    break
                            f.seek(JPGFootStart)
                            if debug >= 2:
                                print('\tSeeking to Data Sector [Bytes]: ' + str(JPGFootStart))

                            JPGFootChunk.append(f.read(JPGFootEnd + 1 - JPGFootStart))
                            JPGData = data + JPGFootChunk
                            jpgs.append(JPGData)

                            if debug >= 2:
                                print('\tJPG MD5 Hash: ' + str(Hasher(JPGData, 'md5')))
                            if debug >= 3:
                                print('\tJPG First Chunk: ' + str(data))
                                print('\tJPG Last Chunk: ' + str(JPGFootChunk))
                                print('\tJPG Chunk: ' + str(JPGData))
                            breaker = True
                            JPGData = []
                            break
                        else:
                            while slider != BytesPerSector:
                                if debug >= 3:
                                    print('\tSearching for JPG end.')
                                byte = sector[slider:slider + 6]
                                if byte == b'\xFF\xD9\x00\x00\x00\x00':
                                    if debug >= 2:
                                        print('\tJPG Footer bytes and offset: ' + str(
                                            (BytesPerSector * FirstDataSector) + counter + slider) + ' : ' + str(byte))
                                    data.append(sector[0:slider + 2])
                                    jpgs.append(data)
                                    if debug >= 2:
                                        print('\tJPG Hash: ' + str(Hasher(data, 'md5')))
                                    endofjpg = True
                                    data = []
                                    break
                                else:
                                    slider += 1
                        if not endofjpg:
                            data.append(sector)
                else:
                    if debug >= 3:
                        print('\tSector offset [Bytes]: ' + str(BytesPerSector * FirstDataSector + counter))
                        print('\tSector Data: ' + str(sector))
                    byte = b''
                    sector = f.read(BytesPerSector)
                    counter += BytesPerSector

                    #except:
                    #error = 'Error: Cannot Find Valid Headers.'
                    #status = False
                    #finally:
        if debug >= 2:
                print('\tTotal JPGs Found: ' + str(len(jpgs)))
                print(error)
    except:
        error = 'Error: Cannot Find JPG Valid Headers.'
        status = False
    finally:
        return status, error


def Hasher(data, hashtype):
    ba = b''
    for x in data:
        ba += bytearray(x)
    if hashtype == 'md5':
        return hashlib.md5(ba).hexdigest()
    elif hashtype == 'sha1':
        return hashlib.sha1(ba).hexdigest()


def signal_handler(signal, frame):
    print('Ctrl+C pressed. Exiting.')
    sys.exit(0)


def Writer(text):
    print('\t' + text)


def Header(volume, outputpath):
    print('')
    print('+--------------------------------------------------------------------------+')
    print('|File Carving Utility.                                                     |')
    print('+---------------------------------------------------------------------------')
    print('|Author: Tahir Khan - tkhan9@gmu.edu                                       |')
    print('+--------------------------------------------------------------------------+')
    print('  Date Run: ' + str(datetime.datetime.now()))
    print('+--------------------------------------------------------------------------+')
    print('  Input Volume: ' + str(volume))
    print('+--------------------------------------------------------------------------+')
    print('  Output Path:  ' + str(outputpath))
    print('+--------------------------------------------------------------------------+')


def Failed(error):
    print('  * Error: ' + str(error))
    print('+--------------------------------------------------------------------------+')
    print('| Failed.                                                                  |')
    print('+--------------------------------------------------------------------------+')
    sys.exit(1)


def FileHashes():
    global jpgs
    global pngs
    global bmps
    global gifs

    print('+--------------------------------------------------------------------------+')
    print('| MD5 Hashes:                                                              |')
    print('+--------------------------------------------------------------------------+')
    if pngs:
        for files in pngs:
            print('| PNG Hash: ' + str(Hasher(files, 'md5')) + '                               |')
    if jpgs:
        for files in jpgs:
            print('| JPG Hash: ' + str(Hasher(files, 'md5')) + '                               |')
    if bmps:
        for files in bmps:
            print('| BMP Hash: ' + str(Hasher(files, 'md5')) + '                               |')
    if gifs:
        for files in gifs:
            print('| GIF Hash: ' + str(Hasher(files, 'md5')) + '                               |')
    print('+--------------------------------------------------------------------------+')


def Completed():
    print('| [*] Completed.                                                           |')
    print('+--------------------------------------------------------------------------+')


signal.signal(signal.SIGINT, signal_handler)


def main(argv):
    try:
        global debug
        verify = False
        opersys = ''
        #parse the command-line arguments
        parser = argparse.ArgumentParser(description="A File system carver.", add_help=True)
        parser.add_argument('-o', '--output', help='The output path to write the files to.', required=True)
        parser.add_argument('-i', '--input', help='The volume to read from.', required=True)
        parser.add_argument('-v', '--verify', help='MD5 hash output files.', action='store_true', required=False)
        parser.add_argument('-d', '--debug', help='The level of debugging.', required=False)
        parser.add_argument('--version', action='version', version='%(prog)s 1.5')
        args = parser.parse_args()
        if args.input:
            volume = args.input
            if not os.path.isfile(volume):
                print('')
                print('Error: File/Volume --> ' + str(volume) + ' does not exist.')
                sys.exit(1)
        if args.output:
            output = args.output
            if not os.path.isdir(output):
                print('')
                print('Error: Directory --> ' + str(output) + ' does not exist.')
                sys.exit(1)
        if args.verify:
            verify = True
        if args.debug:
            debug = args.debug
            debug = int(debug)
        if _platform == "linux" or _platform == "linux2":
            opersys = 'Linux'
        elif _platform == "darwin":
            opersys = 'Mac'
        elif _platform == "win32":
            opersys = 'Windows'
        if debug >= 1:
            print('Entered main:')
            print('\tVolume: ' + str(volume))
            print('\tOperating System: ' + str(opersys))
            print('\tDebug Level: ' + str(debug))
            #if (os == 'Windows'):
            #    print ('Error: System not supported.')
            #    sys.exit(1)

        Header(volume, output)
        status, error, bootsector = IdentifyFileSystem(volume)
        if status:
            print('| [+] Identifying File System.                                             |')
        else:
            print('| [-] Unsupported File System.                                             |')
            Failed(error)
        status, error = ReadBootSector(volume)
        if status:
            print('| [+] Identifying Boot Sector.                                             |')
        else:
            print('| [-] Identifying Boot Sector.                                             |')
            Failed(error)
        status, error = SearchJPGs(volume)
        if status:
            print('| [+] Searching for JPG Data.                                              |')
        else:
            print('| [-] Searching for JPG Data.                                              |')
            Failed(error)
        status, error = SearchGIFs(volume)
        if status:
            print('| [+] Searching for GIF Data.                                              |')
        else:
            print('| [-] Searching for GIF Data.                                              |')
            Failed(error)
        status, error = SearchPNGs(volume)
        if status:
            print('| [+] Searching for PNG Data.                                              |')
        else:
            print('| [-] Searching for PNG Data.                                              |')
            Failed(error)
        status, error = SearchBMPs(volume)
        if status:
            print('| [+] Searching for BMP Data.                                              |')
        else:
            print('| [-] Searching for BMP Data.                                              |')
            Failed(error)
        status, error = WriteDatatoFile(output)
        if status:
            print('| [+] Writing Output.                                                      |')
        else:
            print('| [-] Writing Output.                                                      |')
            Failed(error)
        if verify:
            FileHashes()
        Completed()


    except:
        sys.exit(1)


main(sys.argv[1:])