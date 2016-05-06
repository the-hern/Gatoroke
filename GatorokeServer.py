#!/usr/bin/env python

from pykconstants import *
from pykplayer import pykPlayer
from pykenv import env
from pykmanager import manager
import sys, pygame, os, string, math, time
import pygame.image
import pygame.display
from pygame.locals import *
import bmp
import bmpfont_FreeSansBold_12
import Image, ImageDraw, ImageFont
import cdgPlayer

path = "/var/www/songqueue/"
cdgpath = "/home/hern/A-Z"
#cdgpath = "/home/hern/Karaoke/A-Z"
mp3path = "/home/hern/mp3"
introSleepTime = 10


PAUSED=1
INTRO=2
PLAYING=3
WAITING=4
LIST=5

# Import the optimised C version if available, or fall back to Python
try:
    import _pycdgAux as aux_c
except ImportError:
    aux_c = None

try:
    import pycdgAux as aux_python
except ImportError:
    aux_python = None

import HTMLParser

CDG_DISPLAY_WIDTH   = 288
CDG_DISPLAY_HEIGHT  = 192

# Screen tile positions
# The viewable area of the screen (294x204) is divided into 24 tiles
# (6x4 of 49x51 each). This is used to only update those tiles which
# have changed on every screen update, thus reducing the CPU load of
# screen updates. A bitmask of tiles requiring update is held in
# cdgPlayer.UpdatedTiles.  This stores each of the 4 columns in
# separate bytes, with 6 bits used to represent the 6 rows.
TILES_PER_ROW           = 6
TILES_PER_COL           = 4
TILE_WIDTH              = CDG_DISPLAY_WIDTH / TILES_PER_ROW
TILE_HEIGHT             = CDG_DISPLAY_HEIGHT / TILES_PER_COL

def showKaraokeIntro(songlist):

    singer,song=songlist[0].split(":")
    songname=song.split(" [")[0]
    artist, title = songname.split(" - ", 1)

    image = Image.new("RGBA", (640,480), (255,255,255))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 24)
    draw.text((10, 10), "%s -- %s (%s)" % (singer, title, artist), (0,0,0), font=font)
    font = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", 18)
    for i in range(1,len(songlist)):
        if (100+(i*30)) > 450:
            break
        singer,song=songlist[i].split(":")
        songname=song.split(" [")[0]
        artist, title = songname.split(" - ", 1)
        draw.text((10, (100+(i*30))), "%s -- %s (%s)" % (singer, title, artist), (0,0,0), font=font)
    #str_image=image.tobytes()
    str_image=pygame.image.tobytes(image, 'RGBA')
    picture=pygame.image.fromstring(str_image, (image.size), "RGBA")

    pygame.display.set_mode(picture.get_size(),pygame.FULLSCREEN)
    main_surface = pygame.display.get_surface()
    main_surface.blit(picture,(0,0))
    pygame.display.update()
    time.sleep(introSleepTime)

def playRequestedCDG(singer, songfile):
    songname=songfile.split(" [")[0]
    artist, title = songname.split(" - ", 1)
    player = cdgPlayer('%s/%s' % (cdgpath, songfile), None)
    player.Play()
    manager.WaitForPlayer()

def playRequestedMP3(songfile):
    fontsize=48
    songname=songfile.split(" [")[0]
    artist, title = songname.split(" - ", 1)
 
    txt="Up Next Some Song Sung by Alex"
    image = Image.new("RGBA", (640,480), (255,255,255))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", fontsize)
    draw.text((10, 0), "Now Playing...", (0,0,0), font=font)
    draw.text((10, 100), title,  (0,0,0), font=font)
    draw.text((10, 200), "by - %s" % artist, (0,0,0), font=font)
    #str_image=image.tobytes()
    str_image=pygame.image.tobytes(image, 'RGBA')
    picture=pygame.image.fromstring(str_image, (image.size), "RGBA")

    pygame.display.set_mode(picture.get_size(),pygame.FULLSCREEN)
    main_surface = pygame.display.get_surface()
    main_surface.blit(picture,(0,0))
    pygame.mouse.set_visible(False)
    pygame.display.update()

    pygame.mixer.init()
    pygame.mixer.music.load('%s/%s' % (mp3path, songfile))
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)
    pygame.display.quit()

def waitScreen():
    fontsize=36
    image = Image.new("RGBA", (640,480), (255,255,255))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSansBold.ttf", fontsize)
    draw.text((10, 10), "Waiting for Requests...", (0,0,0), font=font)
    draw.text((10, 100), "Go to http://karaoke.thehern.org",  (0,0,0), font=font)
    draw.text((10, 200), "to put in a request!!!", (0,0,0), font=font)
    str_image=image.tobytes("raw", 'RGBA')
    picture=pygame.image.fromstring(str_image, (image.size), "RGBA")

    drivers = ['directfb', 'fbcon', 'svgalib']
    found = False
    for driver in drivers:
        # Make sure that SDL_VIDEODRIVER is set
        if not os.getenv('SDL_VIDEODRIVER'):
            os.putenv('SDL_VIDEODRIVER', driver)
        try:
            pygame.display.init()
        except pygame.error:
            print 'Driver: {0} failed.'.format(driver)
            continue
        found = True
        break

    if not found:
        raise Exception('No suitable video driver found!')

    size = (pygame.display.Info().current_w, pygame.display.Info().current_h)

    pygame.display.set_mode(picture.get_size(),pygame.FULLSCREEN)
    main_surface = pygame.display.get_surface()
    main_surface.blit(picture,(0,0))
    pygame.mouse.set_visible(False)
    pygame.display.update()
    time.sleep(10)
    pygame.display.quit()

def playRequestedM3U(playlist):
    print 'Playing Playlist: %s' % (playlist)


def defaultErrorPrint(ErrorString):
    print (ErrorString)


def main2():

    songlist = []
    while 1 == 1:
      try:
        dirlist = os.listdir(path)
        dirlist.sort(key=lambda x: os.path.getmtime(os.path.join(path, x)))
        if len(dirlist) > 0:
            if "PAUSE" in dirlist:
                print 'Pausing...'
                time.sleep(10)
                continue
            type=dirlist[0].split(".")[1]
            songname=dirlist[0]
            html_parser=HTMLParser.HTMLParser()
            dirlist[0]=html_parser.unescape(dirlist[0])
            if type == "cdg":
                singer,song=dirlist[0].split(":")
                showKaraokeIntro(dirlist)
                print 'Playing CDG %s(%s)' % (singer, song)
                playRequestedCDG(singer, song)
                os.remove('%s/%s' % (path, songname))
            elif type == "mp3":
                print 'Playing MP3 %s' % (dirlist[0])
                playRequestedMP3(dirlist[0])
                os.remove('%s/%s' % (path, songname))
            elif type == "m3u":
                print 'Playing Songlist %s' % (dirlist[0])
                playRequested3U(dirlist[0])
                os.remove('%s/%s' % (path, songname))
        else:
            waitScreen()
      except Exception, err:
        print 'ERROR: %s, %s' % (str(err), str(Exception))
        sys.exit()


class GatorokeServer():
    def __init__(self):
        drivers = ['directfb', 'fbcon', 'svgalib']
        found = False
        for driver in drivers:
            # Make sure that SDL_VIDEODRIVER is set
            if not os.getenv('SDL_VIDEODRIVER'):
                os.putenv('SDL_VIDEODRIVER', driver)
            try:
                pygame.display.init()
            except pygame.error:
                print 'Driver: {0} failed.'.format(driver)
                continue
            found = True
            break
    
        if not found:
            raise Exception('No suitable video driver found!')
    
        size = (pygame.display.Info().current_w, pygame.display.Info().current_h)

        #Initialize Everything
        pygame.init()
        self.screen = pygame.display.set_mode(size,pygame.FULLSCREEN)
        pygame.display.set_caption('Gatoroake')
        pygame.mouse.set_visible(0)

        #Create The Backgound
        self.background = pygame.Surface(self.screen.get_size())
        self.background = self.background.convert()
        self.background.fill((250, 250, 250))

        #Put Text On The Background, Centered
        if pygame.font:
            self.font = pygame.font.Font(None, 36)
            text = self.font.render("Gatoroake Karaoke", 1, (10, 10, 10))
            textpos = text.get_rect(centerx=self.background.get_width()/2)
            self.background.blit(text, textpos)

        #Display The Background
        self.screen.blit(self.background, (0, 0))
        pygame.display.flip()

        #Prepare Game Objects
        self.clock = pygame.time.Clock()

    def run(self):
        '''
        States in Loop:
        PAUSED
        INTRO
        PLAYING
        WAITING
        LIST
        '''
        state=WAITING
        oldstate=None
        waitCounter = 0
        sleepTime = 10
        songlist = []
        while 1:
            self.screen.blit(self.background, (0, 0))
            pygame.display.flip()
            self.clock.tick(60)
            #Handle Input Events
            for event in pygame.event.get():
                self.checkQuit(event)
                if state == LIST and event.type == KEYDOWN and event.key == K_SPACE:
                    state = INTRO
                elif event.type == KEYDOWN and event.key == K_a:
                    self.writeMessage("a pressed", clearbg=True)
                elif event.type == KEYDOWN and event.key == K_p:
                    if state == PAUSED:
                        state = oldstate
                    else:
                        oldstate = state
                        state = PAUSED
            if state == PAUSED:
                self.writeMessage('Paused\nPress "P" to continue', clearbg=True)
                continue
            if state == WAITING:
                requestList = self.getDirList()
                if requestList != None and len(requestList) > 0:
                    state = LIST
                else:
                    self.writeMessage("Checking Queue...", clearbg=True)
                    continue
            elif state == LIST:
                displayString = self.formatRequestString(requestList)
                self.writeMessage("Upcoming Singers:\n%s\n\nSPACE to continue" %displayString, clearbg = True)
            elif state == INTRO:
                #Intro Timer
                if waitCounter > (sleepTime * 100):
                    waitCounter = 0
                    state = WAITING
                    self.playSong(requestList)
                    continue
                waitCounter += 1
                self.writeMessage("Intro Screen Countdown: %d" %(10 - (waitCounter / 100)), clearbg = True)
                #showKaraokeIntro(requestList)
                continue

    def formatRequestString(self, requestList):
        retString = ""
        for i in range(0,len(requestList)):
            if (100+(i*30)) > 450:
                break
            singer,song=requestList[i].split(":")
            songname=song.split(" [")[0]
            artist, title = songname.split(" - ", 1)
            #retString = "%s\n%s - %s" %(retString, singer, title)
            retString = "%s\n%s" %(retString, song)
        return retString

    def playSong(self, requestList):
        songname=requestList[0]
        html_parser=HTMLParser.HTMLParser()
        requestList[0]=html_parser.unescape(requestList[0])
        type=requestList[0].split(".")[1]
        if type == "cdg":
            singer,song=requestList[0].split(":")
            print 'Playing CDG %s(%s)' % (singer, song)
            #playRequestedCDG(singer, song)
            os.remove('%s/%s' % (path, songname))
        elif type == "mp3":
            print 'Playing MP3 %s' % (requestList[0])
            #playRequestedMP3(requestList[0])
            os.remove('%s/%s' % (path, songname))
        elif type == "m3u":
            print 'Playing Songlist %s' % (requestList[0])
            #playRequested3U(dirlist[0])
            os.remove('%s/%s' % (path, songname))

    def getDirList(self):
        try:
            dirlist = os.listdir(path)
            dirlist.sort(key=lambda x: os.path.getmtime(os.path.join(path, x)))
        except Exception, err:
            print 'ERROR: %s, %s' % (str(err), str(Exception))
            return None
        return dirlist

    def sleep(self, seconds):
        count = 0
        while count < seconds * 60:
            count += 1
            self.clock.tick(60)
            for event in pygame.event.get():
                self.checkQuit(event)
            self.screen.blit(self.background, (0, 0))
            pygame.display.flip()
        return
        
    def checkQuit(self, event):
        if event.type == QUIT:
            sys.exit(0)
        elif event.type == KEYDOWN and event.key == K_ESCAPE:
            sys.exit(0)

    def resetBackground(self):
        self.background.fill((250, 250, 250))
        self.screen.blit(self.background, (0, 0))
        pygame.display.flip()

    def writeMessage(self, message, size=36, clearbg=False):
        if clearbg == True:
            self.resetBackground()
        text = self.font.render(message, True, (10, 10, 10))
        textrect = text.get_rect()
        #textrect.centerx = self.background.get_width()/2
        textrect.centery = self.background.get_height()/2
        for line in message.split('\n'):
            text = self.font.render(line, True, (10, 10, 10))
            textrect.centery += 30
            self.background.blit(text, textrect)

    def waitScreen(self):
        self.writeMessage("Waiting for Requests...", clearbg=True)

def main():
    myServer = GatorokeServer()
    myServer.run()


if __name__ == "__main__":
    sys.exit(main())

