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
SKIP=6

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
PG_DISPLAY_WIDTH   = 800
PG_DISPLAY_HEIGHT  = 600

class GatorokeServer():
    def __init__(self):
        '''
        drivers = ['fbcon','directfb', 'svgalib']
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
        '''
        self.displayInit()
    
    def displayInit(self):
        pygame.init()
        self.screen = pygame.display.set_mode([PG_DISPLAY_WIDTH, PG_DISPLAY_HEIGHT])
        pygame.display.set_caption('Gatoroke')
        pygame.mouse.set_visible(0)

        self.background = pygame.Surface((PG_DISPLAY_WIDTH, PG_DISPLAY_HEIGHT))

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
        return

    def displayQuit(self):
        pygame.display.quit()
	time.sleep(2)
        return

    def run(self):
        '''
        States in Loop:
        PAUSED
        INTRO
        PLAYING
        WAITING
        LIST
        SKIP
        '''
        state=WAITING
        oldstate=None
        waitCounter = 0
        sleepTime = 2
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
                elif state == LIST and event.type == KEYDOWN and event.key == K_s:
                    state = SKIP
            if state == PAUSED:
                self.writeMessage('Paused\nPress "P" to continue', clearbg=True)
                continue
            if state == WAITING:
                requestList = self.getDirList()
                if requestList != None and len(requestList) > 0:
                    state = LIST
                else:
                    self.writeMessage("Waiting for Requests\n\nhttp://gatoroke", clearbg=True)
                    continue
            if state == SKIP:
                self.skipNextSinger(requestList)
                state = LIST
                continue
            elif state == LIST:
                requestList = self.getDirList()
                if len(requestList) == 0:
                    state = WAITING
                    continue
                displayString = self.formatRequestString(requestList)
                self.writeMessage("Upcoming Singers:\n%s\n\nSPACE to continue, S to Skip" %displayString, clearbg = True)
            elif state == INTRO:
                #Intro Timer
                if waitCounter > (sleepTime * 100):
                    waitCounter = 0
                    state = WAITING
                    self.playSong(requestList)
                    continue
                waitCounter += 1
                self.writeMessage("Intro Screen Countdown: %d" %(sleepTime - (waitCounter / 100)), clearbg = True)
                #showKaraokeIntro(requestList)
                continue

    def skipNextSinger(self, requestList):
        songname=requestList[0]
        os.remove('%s/%s' % (path, songname))

    def playRequestedCDG(self, singer, songfile):
        self.displayQuit()
        songname=songfile.split(" [")[0]
        artist, title = songname.split(" - ", 1)
        player = cdgPlayer.cdgPlayer('%s/%s' % (cdgpath, songfile), None)
        player.Play()
        manager.WaitForPlayer()
        self.displayInit()

    def formatRequestString(self, requestList):
        retString = ""
        for i in range(0,len(requestList)):
            if i > 4:
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
            self.playRequestedCDG(singer, song)
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
        message_list = message.split('\n')
        maxLine=''
        for line in message_list:
            if len(line) > len(maxLine):
                maxLine = line

        text = self.font.render(maxLine, True, (10, 10, 10))
        textrect = text.get_rect()
        textrect.centerx = self.background.get_width()/2
        textrect.centery = (self.background.get_height()/2) - (len(message_list) * 15)
        center_y = textrect.centery
        #textrect.centery = self.background.get_height()/2
        for line in message_list:
            text = self.font.render(line, True, (10, 10, 10))
            textrect = text.get_rect()
            textrect.centerx = self.background.get_width()/2
            center_y += 30
            textrect.centery = center_y
            self.background.blit(text, textrect)

    def waitScreen(self):
        self.writeMessage("Waiting for Requests...", clearbg=True)

def main():
    myServer = GatorokeServer()
    myServer.run()


if __name__ == "__main__":
    sys.exit(main())

