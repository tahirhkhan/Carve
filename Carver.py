__author__ = 'khanta'

#Create Disk  --> dd if=/dev/zero of=512MB.dd bs=1M count=512
#Create FAT32 --> mkdosfs -n 512MB -F 32 -v 512MB.dd
import os
import sys
import argparse
import datetime
import signal
import struct
import hashlib
from array import array
from sys import platform as _platform
import ntpath

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

EndOfChain = 0x0fffffff
EndOfFile = 0x0fffffff
EmptyCluster = 0x00000000
DamagedCluster = 0x0ffffff7
ValidBytesPerSector = [512, 1024, 2048, 4096]

MD5HashValue = ''

JPGHeader = 0xFFD8
JPGFooter = 0xFFD9
BMPHeader = 0x4D42

StartOffset = ''
EndOffset = ''

# </editor-fold>


def HashMD5(file, block_size=2 ** 20):
    if (debug >= 1):
        print('Entering HashMD5:')
    md5 = hashlib.md5()
    with open(file, 'rb') as f:
        while True:
            data = f.read(block_size)
            if not data:
                break
            md5.update(data)
    return md5.hexdigest()


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
    global BootSector
    global TotalFAT32Sectors
    global TotalFAT32Bytes
    global DataAreaStart
    global DataAreaEnd
    global FirstDataSector
    # </editor-fold>
    status = True
    error = ''

    # Reads the specified bytes from the drive
    try:
        if (debug >= 1):
            print('Entering ReadBootSector:')
        with open(volume, "rb") as f:
            bytes = f.read(BootSectorSize)
            BytesPerSector = struct.unpack("<H", bytes[11:13])[0]
            if (BytesPerSector not in ValidBytesPerSector):
                print('Error: This is not a FAT32 drive.')
            SectorsPerCluster = struct.unpack("<b", bytes[13:14])[0]
            ReservedSectorCount = struct.unpack("<H", bytes[14:16])[0]
            NumberOfFATs = struct.unpack("<b", bytes[16:17])[0]
            TotalSectors = struct.unpack("i", bytes[32:36])[0]
            FAT32Size = struct.unpack("i", bytes[36:40])[0]
            RootCluster = struct.unpack("i", bytes[44:48])[0]
            FSInfoSector = struct.unpack("<H", bytes[48:50])[0]

            #Calculate some values
            ClusterSize = SectorsPerCluster * BytesPerSector
            TotalFAT32Sectors = FAT32Size * NumberOfFATs
            TotalFAT32Bytes = FAT32Size * BytesPerSector

            DataAreaStart = ReservedSectorCount + TotalFAT32Sectors
            DataAreaEnd = TotalSectors - 1  #Base 0
            #Double Check per MS Documentation
            #FirstDataSector = BPB_ReservedSecCnt + (BPB_NumFATs * FATSz) + RootDirSectors;
            FirstDataSector = ReservedSectorCount + (NumberOfFATs * FAT32Size) + RootDirSectors
            if (debug >= 1):
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


def find_missing_range(numbers, min, max):
    expected_range = set(range(min, max + 1))
    return sorted(expected_range - set(numbers))


def numbers_as_ranges(numbers):
    ranges = []
    for number in numbers:
        if ranges and number == (ranges[-1][-1] + 1):
            ranges[-1] = (ranges[-1][0], number)
        else:
            ranges.append((number, number))
    return ranges


def format_ranges(ranges):
    range_iter = (("%d" % r[0] if r[0] == r[1] else "%d-%d" % r) for r in ranges)
    return "(" + ", ".join(range_iter) + ")"


def SearchFAT(volume, FATOffset, FirstCluster):
    status = True
    error = ''
    global ReadClusterList

    try:
        if (debug >= 1):
            print('Entering SearchFAT:')
            print('\tFirstCluster passed in: ' + str(FirstCluster))
            print('\tVolume passed in: ' + str(volume))

        nextcluster = FirstCluster
        ReadClusterList.append(nextcluster)
        y = 0
        with open(volume, "rb") as f:
            f.seek(FATOffset * BytesPerSector)
            bytes = f.read(TotalFAT32Bytes)
            if (debug >= 2):
                print('\tSeeking to FAT Offset (Bytes): ' + str(FATOffset * BytesPerSector))
            while (y <= TotalFAT32Bytes):
                y += 4
                chunk = bytes[nextcluster * 4:nextcluster * 4 + 4]
                nextcluster = struct.unpack("<i", chunk)[0]
                if (debug >= 3):
                    print('\tCluster Read [Length]: ' + '[' + str(len(chunk)) + ']' + str(chunk))
                if (debug >= 2):
                    print('\tNext Cluster: ' + str(nextcluster))
                if (nextcluster != 268435455):
                    ReadClusterList.append(nextcluster)
                else:
                    break
        if (debug >= 2):
            print('\tCluster List: ' + str(ReadClusterList))
            #return ReadClusterList
    except:
        error = 'Error: Cannot Search FAT.'
        status = False
    finally:
        return status, error


def ReadData(volume, clusterlist, size):
    status = True
    error = ''
    global FileData
    try:
        if (debug >= 1):
            print('Entering ReadData:')
        if (debug >= 2):
            print('Volume Passed in: ' + str(volume))
            print('Clusterlist Passed in: ' + str(clusterlist))
            print('Size in: ' + str(size))
        readchunk = bytearray()
        with open(volume, "rb") as f:
            for cluster in clusterlist:  #New Offset is 2 (Cluster)
                seeker = (cluster * ClusterSize + (DataAreaStart * BytesPerSector) - 2 * ClusterSize)
                f.seek(seeker)  #Each ClusterNum - 2 (Offset) * Bytes per cluster + (DataAreaStart * BytesPerSector)
                if (debug >= 2):
                    print('\tSeeking to Cluster (Bytes) [Cluster]: ' + '[' + str(cluster) + ']' + str(seeker))
                readchunk += f.read(ClusterSize)
            FileData = readchunk[0:size]
            if (debug >= 3):
                print('\tFile Data: ' + str(FileData))
    except:
        error = ('Error: Cannot Read Data.')
        status = False
    finally:
        return status, error


def WriteDatatoFile(file, filedata):
    status = True
    error = ''
    global FileData
    global MD5HashValue
    try:
        if (debug >= 1):
            print('Entering WriteDatatoFile:')
        if not (FileData == ''):
            with open(file, "wb") as f:
                f.write(FileData)
            md5 = hashlib.md5()
            md5.update(FileData)
            MD5HashValue = md5.hexdigest()
        else:
            error = 'File Data is Emtpy.'
    except:
        error = 'Error: Cannot Write Data.'
        status = False
    finally:
        return status, error


def SearchDataJPG(volume):
    status = True
    error = ''

    try:
        if (debug >= 1):
            print('Entering SearchDataJPG:')
        if (debug >= 2):
            print('Volume Passed in: ' + str(volume))
        readchunk = bytearray()
        with open(volume, "rb") as f:
            if (debug >= 2):
                print('\tSeeking to First Data Sector [Bytes]: ' + str(BytesPerSector * FirstDataSector))
            x = 0
            while (True):
                f.seek(BytesPerSector * FirstDataSector + x)
                bytes = f.read(16)  #Size of FAT32 Directory
                firstchar = struct.unpack("H", bytes[0:2])[0]
                if (firstchar == 0xFFD8):
                    print('JPG Header Found at Offset: ' + str(BytesPerSector * FirstDataSector + x))
                    break
                else:
                    x += 16
    except:
        error = 'Error: Cannot Find Valid Headers.'
        status = False
    finally:
        return status, error


def SearchDataBMP(volume):
    status = True
    error = ''

    try:
        if (debug >= 1):
            print('Entering SearchDataBMP:')
        if (debug >= 2):
            print('Volume Passed in: ' + str(volume))
        readchunk = bytearray()
        with open(volume, "rb") as f:
            if (debug >= 2):
                print('\tSeeking to First Data Sector [Bytes]: ' + str(BytesPerSector * FirstDataSector))
            x = 0
            while (True):
                f.seek(BytesPerSector * FirstDataSector + x)
                bytes = f.read(16)  #Size of FAT32 Directory
                firstchar = struct.unpack("H", bytes[0:2])[0]
                if (firstchar == 0x4D42):
                    print('BMP Header Found at Offset: ' + str(BytesPerSector * FirstDataSector + x))
                    break
                else:
                    x += 16


    except:
        error = 'Error: Cannot Find Valid Headers.'
        status = False
    finally:
        return status, error


def ReadDataJPG(volume):


def signal_handler(signal, frame):
    print('Ctrl+C pressed. Exiting.')
    sys.exit(0)


def Header():
    print('')
    print('+------------------------------------------------------------------------+')
    print('|FAT32 File Carving Utility.                                             |')
    print('+-------------------------------------------------------------------------')
    print('|Author: Tahir Khan - tkhan9@gmu.edu                                     |')
    print('+------------------------------------------------------------------------+')
    print('  Date Run: ' + str(datetime.datetime.now()))
    print('+------------------------------------------------------------------------+')


def Failed(error):
    print('  * Error: ' + str(error))
    print('+------------------------------------------------------------------------+')
    print('| Failed.                                                                |')
    print('+------------------------------------------------------------------------+')
    sys.exit(1)


def Completed():
    print('| Completed.                                                             |')
    print('+------------------------------------------------------------------------+')
    #print('  File: ' + str(ntpath.basename(file)) + ' - ' + 'MD5: ' + str(MD5HashValue))
    print('+------------------------------------------------------------------------+')
    sys.exit(0)



signal.signal(signal.SIGINT, signal_handler)


def main(argv):
    #try:
    global debug
        global MD5HashValue
        #parse the command-line arguments
        fragments = int(0)
        write = False
        status = True
        error = ''
        parser = argparse.ArgumentParser(description="A FAT32 file system writer that forces fragmentation.",
                                         add_help=True)
    parser.add_argument('-p', '--path', help='The path to write the files to.', required=True)
    parser.add_argument('-v', '--volume', help='The volume to read from.', required=True)
    parser.add_argument('-d', '--debug', help='The level of debugging.', required=False)
    parser.add_argument('-s', '--search', help='Search for JPG/BMP.', action='store_true', required=True)
    parser.add_argument('--version', action='version', version='%(prog)s 1.5')
        args = parser.parse_args()
        if (args.volume):
            volume = args.volume
        if (args.search):
            search = args.search
        if (args.debug):
            debug = args.debug
            debug = int(debug)
        if _platform == "linux" or _platform == "linux2":
            os = 'Linux'
        elif _platform == "darwin":
            os = 'Mac'
        elif _platform == "win32":
            os = 'Windows'
        if (debug >= 1):
            print('Entered main:')
            print('\tVolume: ' + str(volume))
            print('\tOperating System: ' + str(os))
            print('\tDebug Level: ' + str(debug))
            #if (os == 'Windows'):
            #    print ('Error: System not supported.')
            #    sys.exit(1)



        #=======================================================================================================================
    Header()
    status, error = ReadBootSector(volume)
        if (status):
            print('| + Reading Boot Sector.                                                 |')
        else:
            print('| - Reading Boot Sector.                                                 |')
            Failed(error)
    if (search):
        status, error = SearchDataJPG(volume)
        if (status):
                print('| + Searching Data.                                                      |')
            else:
                print('| - Searching Data.                                                      |')
                Failed(error)
    if (search):
        status, error = SearchDataBMP(volume)
        if (status):
            print('| + Searching Data.                                                      |')
        else:
            print('| - Searching Data.                                                      |')
            Failed(error)
            #status, error = WriteDatatoFile(file, FileData)
            #if (status):
            #print('| + Writing File.                                                        |')
            #else:
            #print('| - Writing File.                                                        |')
            #Failed(error)
        Completed()
        #except:
        #    print()


main(sys.argv[1:])