#!/usr/bin/env python


from pykconstants import *
from pykplayer import pykPlayer
from pykenv import env
from pykmanager import manager
import sys, pygame, os, string, math, time
import pygame.image
import pygame.display
import bmp
import bmpfont_FreeSansBold_12
import Image, ImageDraw, ImageFont

# Import the optimised C version if available, or fall back to Python
try:
    import _pycdgAux as aux_c
except ImportError:
    aux_c = None

try:
    import pycdgAux as aux_python
except ImportError:
    aux_python = None


CDG_DISPLAY_WIDTH   = 288
CDG_DISPLAY_HEIGHT  = 192
#CDG_DISPLAY_WIDTH   = 1366
#CDG_DISPLAY_HEIGHT  = 768

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

# cdgPlayer Class
class cdgPlayer(pykPlayer):
    # Initialise the player instace
    def __init__(self, song, songDb, errorNotifyCallback=None,
                 doneCallback=None):
        """The first parameter, song, may be either a pykdb.SongStruct
        instance, or it may be a filename. """

        pykPlayer.__init__(self, song, songDb, errorNotifyCallback, doneCallback)


        # Setup FullScreen Mode
        manager.settings.FullScreen = 1
        manager.settings.PlayerSize = (manager.options.size_x, manager.options.size_y)
        manager.displayFlags |= pygame.FULLSCREEN


        # With the nomusic option no music will be played.

        soundFileData = None
        if not manager.options.nomusic:
            # Check for a matching mp3 or ogg file.  Check extensions
            # in the following order.
            validexts = [
                '.wav', '.ogg', '.mp3'
            ]

            for ext in validexts:
                for data in self.SongDatas:
                    if data.Ext == ext:
                        # Found a match!
                        soundFileData = data
                        break
                if soundFileData:
                    break

            if not soundFileData:
                ErrorString = "There is no mp3 or ogg file to match " + self.Song.DisplayFilename
                self.ErrorNotifyCallback (ErrorString)
                raise 'NoSoundFile'

        self.cdgFileData = self.SongDatas[0]
        self.soundFileData = soundFileData
        self.soundLength = 0

        # Handle a bug in pygame (pre-1.7) which means that the position
        # timer carries on even when the song has been paused.
        self.pauseOffsetTime = 0

        manager.settings.CdgZoom = 'full'
        manager.InitPlayer(self)
        #manager.OpenDisplay(displaySize=[CDG_DISPLAY_WIDTH, CDG_DISPLAY_HEIGHT])
        manager.OpenDisplay()
        manager.surface.fill((0, 0, 0))

        # A working surface for blitting tiles, one at a time.
        self.workingTile = pygame.Surface((TILE_WIDTH, TILE_HEIGHT),
                                          0, manager.surface)

        # A surface that contains the set of all tiles as they are to
        # be assembled onscreen.  This surface is kept at the original
        # scale, then zoomed to display size.  It is only used if
        # settings.CdgZoom == 'soft'.
        self.workingSurface = pygame.Surface((CDG_DISPLAY_WIDTH, CDG_DISPLAY_HEIGHT),
                                             pygame.HWSURFACE,
                                             manager.surface)

        self.borderColour = None
        self.computeDisplaySize()

        aux = aux_c
        if not aux or not manager.settings.CdgUseC:
            print "Using Python implementation of CDG interpreter."
            aux = aux_python

        # Open the cdg and sound files
        self.packetReader = aux.CdgPacketReader(self.cdgFileData.GetData(), self.workingTile)
        manager.setCpuSpeed('cdg')

        if self.soundFileData:
            # Play the music normally.
            audioProperties = None
            if manager.settings.UseMp3Settings:
                audioProperties = self.getAudioProperties(self.soundFileData)
            if audioProperties == None:
                audioProperties = (None, None, None)
            try:
                manager.OpenAudio(*audioProperties)
                audio_path = self.soundFileData.GetFilepath()
                if type(audio_path) == unicode:
                    audio_path = audio_path.encode(sys.getfilesystemencoding())
                pygame.mixer.music.load(audio_path)
            except:
                self.Close()
                raise

            # Set an event for when the music finishes playing
            pygame.mixer.music.set_endevent(pygame.USEREVENT)

            # Account for the size of the playback buffer in the lyrics
            # display.  Assume that the buffer will be mostly full.  On a
            # slower computer that's struggling to keep up, this may not
            # be the right amount of delay, but it should usually be
            # pretty close.
            self.InternalOffsetTime = -manager.GetAudioBufferMS()

        else:
            # Don't play anything.
            self.InternalOffsetTime = 0

        # Set the CDG file at the beginning
        self.cdgReadPackets = 0
        self.cdgPacketsDue = 0
        self.LastPos = self.curr_pos = 0

        # Some session-wide constants.
        self.ms_per_update = (1000.0 / manager.options.fps)

    def doPlay(self):
        if self.soundFileData:
            pygame.mixer.music.play()

    # Pause the song - Use Pause() again to unpause
    def doPause(self):
        if self.soundFileData:
            pygame.mixer.music.pause()
            self.PauseStartTime = self.GetPos()

    def doUnpause(self):
        if self.soundFileData:
            self.pauseOffsetTime = self.pauseOffsetTime + (self.GetPos() - self.PauseStartTime)
            pygame.mixer.music.unpause()

    # you must call Play() to restart. Blocks until pygame is initialised
    def doRewind(self):
        # Reset the state of the packet-reading thread
        self.cdgReadPackets = 0
        self.cdgPacketsDue = 0
        self.LastPos = 0
        # No need for the Pause() fix anymore
        self.pauseOffsetTime = 0
        # Move file pointer to the beginning of the file
        self.packetReader.Rewind()

        if self.soundFileData:
            # Actually stop the audio
            pygame.mixer.music.rewind()
            pygame.mixer.music.stop()

    def GetLength(self):
        """Give the number of seconds in the song."""
        return self.soundLength

    # Get the current time (in milliseconds). Blocks if pygame is
    # not initialised yet.
    def GetPos(self):
        if self.soundFileData:
            return pygame.mixer.music.get_pos()
        else:
            return pykPlayer.GetPos(self)

    def SetupOptions(self):
        """ Initialise and return optparse OptionParser object,
        suitable for parsing the command line options to this
        application. """

        parser = pykPlayer.SetupOptions(self, usage = "%prog [options] <CDG file>")

        # Remove irrelevant options.
        parser.remove_option('--font-scale')

        return parser


    def shutdown(self):
        # This will be called by the pykManager to shut down the thing
        # immediately.
        if self.soundFileData:
            if manager.audioProps:
                pygame.mixer.music.stop()

        # Make sure our surfaces are deallocated before we call up to
        # CloseDisplay(), otherwise bad things can happen.
        self.workingSurface = None
        self.workingTile = None
        self.packetReader = None
        pykPlayer.shutdown(self)

    def doStuff(self):
        pykPlayer.doStuff(self)

        # Check whether the songfile has moved on, if so
        # get the relevant CDG data and update the screen.
        if self.State == STATE_PLAYING or self.State == STATE_CAPTURING:
            self.curr_pos = self.GetPos() + self.InternalOffsetTime + manager.settings.SyncDelayMs - self.pauseOffsetTime

            self.cdgPacketsDue = int((self.curr_pos * 300) / 1000)
            numPackets = self.cdgPacketsDue - self.cdgReadPackets
            if numPackets > 0:
                if not self.packetReader.DoPackets(numPackets):
                    # End of file.
                    #print "End of file on cdg."
                    self.Close()
                self.cdgReadPackets += numPackets

            # Check if any screen updates are now due.
            if (self.curr_pos - self.LastPos) > self.ms_per_update:
                self.cdgDisplayUpdate()
                self.LastPos = self.curr_pos

    def handleEvent(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN and (event.mod & (pygame.KMOD_LSHIFT | pygame.KMOD_RSHIFT | pygame.KMOD_LMETA | pygame.KMOD_RMETA)):
            # Shift/meta return: start/stop song.  Useful for keybinding apps.
            self.Close()
            return
        
        pykPlayer.handleEvent(self, event)

    def doResize(self, newSize):
        self.computeDisplaySize()

        if self.borderColour != None:
            manager.surface.fill(self.borderColour)

        self.packetReader.MarkTilesDirty()

    def computeDisplaySize(self):
        """ Figures out what scale and placement to use for blitting
        tiles to the screen.  This must be called at startup, and
        whenever the window size changes. """

        winWidth, winHeight = manager.displaySize

        # Compute an appropriate uniform scale to letterbox the image
        # within the window
        scale = min(float(winWidth) / CDG_DISPLAY_WIDTH,
                    float(winHeight) / CDG_DISPLAY_HEIGHT)
        if manager.settings.CdgZoom == 'none':
            scale = 1
        elif manager.settings.CdgZoom == 'int':
            if scale < 1:
                scale = 1.0/math.ceil(1.0/scale)
            else:
                scale = int(scale)
        self.displayScale = scale

        scaledWidth = int(scale * CDG_DISPLAY_WIDTH)
        scaledHeight = int(scale * CDG_DISPLAY_HEIGHT)

        if manager.settings.CdgZoom == 'full':
            # If we are allowing non-proportional scaling, allow
            # scaledWidth and scaledHeight to be independent.
            scaledWidth = winWidth
            scaledHeight = winHeight

        # And the center of the display after letterboxing.
        self.displayRowOffset = (winWidth - scaledWidth) / 2
        self.displayColOffset = (winHeight - scaledHeight) / 2

        # Calculate the scaled width and height for each tile
        if manager.settings.CdgZoom == 'soft':
            self.displayTileWidth = CDG_DISPLAY_WIDTH / TILES_PER_ROW
            self.displayTileHeight = CDG_DISPLAY_HEIGHT / TILES_PER_COL
        else:
            self.displayTileWidth = scaledWidth / TILES_PER_ROW
            self.displayTileHeight = scaledHeight / TILES_PER_COL

    def getAudioProperties(self, soundFileData):
        """ Attempts to determine the samplerate, etc., from the
        specified filename.  It would be nice to know this so we can
        configure the audio hardware to the same properties, to
        minimize run-time resampling. """

        # Ideally, SDL would tell us this (since it knows!), but
        # SDL_mixer doesn't provide an interface to query this
        # information, so we have to open the soundfile separately and
        # try to figure it out ourselves.

        audioProperties = None
        if soundFileData.Ext == '.mp3':
            audioProperties = self.getMp3AudioProperties(soundFileData)

        return audioProperties

    def getMp3AudioProperties(self, soundFileData):
        """ Attempts to determine the samplerate, etc., from the
        specified filename, which is known to be an mp3 file. """

        # Hopefully we have Mutagen available to pull out the song length
        try:
            import mutagen.mp3
        except:
            print "Mutagen not available, will not be able to determine extra MP3 information."
            self.soundLength = 0
            return None

        # Open the file with mutagen
        m = mutagen.mp3.MP3(soundFileData.GetFilepath())

        # Pull out the song length
        self.soundLength = m.info.length

        # Get the number of channels, mode field of 00 or 01 indicate stereo
        if m.info.mode < 2:
            channels = 2
        else:
            channels = 1

        # Put the channels and sample rate together in a tuple and return
        audioProperties = (m.info.sample_rate, -16, channels)
        return audioProperties

    # Actually update/refresh the video output
    def cdgDisplayUpdate(self):
        # This routine is responsible for taking the unscaled output
        # pixel data from self.cdgSurfarray, scaling it and blitting
        # it to the actual display surface. The viewable area of the
        # unscaled surface is 294x204 pixels.  Because scaling and
        # blitting are heavy operations, we divide the screen into 24
        # tiles, and only scale and blit those tiles which have been
        # updated recently.  The CdgPacketReader class
        # (self.packetReader) is responsible for keeping track of
        # which areas of the screen have been modified.

        # There are four different approaches for blitting tiles onto
        # the display:

        # settings.CdgZoom == 'none':
        #   No scaling.  The CDG graphics are centered within the
        #   display.  When a tile is dirty, it is blitted directly to
        #   manager.surface.  After all dirty tiles have been blitted,
        #   we then use display.update to flip only those rectangles
        #   on the screen that have been blitted.

        # settings.CdgZoom = 'quick':
        #   Trivial scaling.  Similar to 'none', but each tile is
        #   first scaled to its target scale using
        #   pygame.transform.scale(), which is quick but gives a
        #   pixelly result.  The scaled tile is then blitted to
        #   manager.surface.

        # settings.CdgZoom = 'int':
        #   The same as 'quick', but the scaling is constrained to be
        #   an integer multiple or divisor of its original size, which
        #   may reduce artifacts somewhat.

        # settings.CdgZoom = 'full':
        #   The same as 'quick', but the scaling is allowed to
        #   completely fill the window in both x and y, regardless of
        #   aspect ratio constraints.

        # settings.CdgZoom = 'soft':
        #   Antialiased scaling.  We blit all tiles onto
        #   self.workingSurface, which is maintained as the non-scaled
        #   version of the CDG graphics, similar to 'none'.  Then,
        #   after all dirty tiles have been blitted to
        #   self.workingSurface, we use pygame.transform.rotozoom() to
        #   make a nice, antialiased scaling of workingSurface to
        #   manager.surface, and then flip the whole display.  (We
        #   can't scale and blit the tiles one a time in this mode,
        #   since that introduces artifacts between the tile edges.)
        borderColour = self.packetReader.GetBorderColour()
        if borderColour != self.borderColour:
            # When the border colour changes, blit the whole screen
            # and redraw it.
            self.borderColour = borderColour
            if borderColour != None:
                manager.surface.fill(borderColour)
                self.packetReader.MarkTilesDirty()

        dirtyTiles = self.packetReader.GetDirtyTiles()
        if not dirtyTiles:
            # If no tiles are dirty, don't bother.
            return

        # List of update rectangles (in scaled output window)
        rect_list = []

        # Scale and blit only those tiles which have been updated
        for row, col in dirtyTiles:
            self.packetReader.FillTile(self.workingTile, row, col)

            if manager.settings.CdgZoom == 'none':
                # The no-scale approach.
                rect = pygame.Rect(self.displayTileWidth * row + self.displayRowOffset,
                                   self.displayTileHeight * col + self.displayColOffset,
                                   self.displayTileWidth, self.displayTileHeight)
                manager.surface.blit(self.workingTile, rect)
                rect_list.append(rect)

            elif manager.settings.CdgZoom == 'soft':
                # The soft-scale approach.
                self.workingSurface.blit(self.workingTile, (self.displayTileWidth * row, self.displayTileHeight * col))

            else:
                # The quick-scale approach.
                scaled = pygame.transform.scale(self.workingTile, (self.displayTileWidth,self.displayTileHeight))
                rect = pygame.Rect(self.displayTileWidth * row + self.displayRowOffset,
                                   self.displayTileHeight * col + self.displayColOffset,
                                   self.displayTileWidth, self.displayTileHeight)
                manager.surface.blit(scaled, rect)
                rect_list.append(rect)

        if manager.settings.CdgZoom == 'soft':
            # Now scale and blit the whole screen.
            scaled = pygame.transform.rotozoom(self.workingSurface, 0, self.displayScale)
            manager.surface.blit(scaled, (self.displayRowOffset, self.displayColOffset))
            manager.Flip()
        elif len(rect_list) < 24:
            # Only update those areas which have changed
            if manager.display:
                pygame.display.update(rect_list)
        else:
            manager.Flip()



# Can be called from the command line with the CDG filepath as parameter
def main():
    player = cdgPlayer(None, None)
    player.Play()
    manager.WaitForPlayer()

if __name__ == "__main__":
    sys.exit(main())
    #import profile
    #result = profile.run('main()', 'pycdg.prof')
    #sys.exit(result)
