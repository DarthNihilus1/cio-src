"""
COG INVASION ONLINE
Copyright (c) CIO Team. All rights reserved.

@file DistributedDodgeballGame.py
@author Brian Lach
@date April 18, 2016

OMG FINALLY THE DODGEBALL GAME!!

"""

from panda3d.core import Fog, Point3, Vec3, VBase4, TextNode

from direct.directnotify.DirectNotifyGlobal import directNotify
from direct.fsm.State import State
from direct.interval.IntervalGlobal import Sequence, Wait, Func, LerpPosInterval, Parallel, LerpScaleInterval
from direct.gui.DirectGui import OnscreenText

from src.coginvasion.globals import CIGlobals
from src.coginvasion.hood import ZoneUtil
from src.coginvasion.toon import ParticleLoader
from src.coginvasion.toon.ToonDNA import ToonDNA

if game.process == 'client':
    from src.coginvasion.base import ToontownIntervals

from DistributedMinigame import getAlertText, getAlertPulse
from DistributedEagleGame import getGameText, getCountdownIval, getRoundIval
from DistributedToonFPSGame import DistributedToonFPSGame
from DodgeballFirstPerson import DodgeballFirstPerson
from Snowball import Snowball
from TeamMinigame import TeamMinigame

from DodgeballGlobals import *

import random

from RemoteDodgeballAvatar import RemoteDodgeballAvatar

class DistributedDodgeballGame(DistributedToonFPSGame, TeamMinigame):
    """The winter dodgeball minigame (client side)"""

    notify = directNotify.newCategory("DistributedDodgeballGame")

    TreeData = [['prop_snow_tree_small_ur', Point3(23.23, 66.52, 7.46)],
	            ['prop_snow_tree_small_ul', Point3(-34.03, 88.02, 24.17)],
	            ['prop_snow_tree_small_ur', Point3(-54.80, 0, 4.19)],
	            ['prop_snow_tree_small_ul', Point3(54.80, -5, 4.19)],
	            ['prop_snow_tree_small_ur', Point3(62.71, 62.66, 16.80)],
	            ['prop_snow_tree_small_ul', Point3(-23.23, -66.52, 6)],
	            ['prop_snow_tree_small_ur', Point3(34.03, -88.02, 23)],
	            ['prop_snow_tree_small_ul', Point3(-62.71, -62.66, 16)]]

    SnowballData = [Point3(30, 0, 0.75),
                    Point3(22.5, 0, 0.75),
                    Point3(15, 0, 0.75),
                    Point3(7.5, 0, 0.75),
                    Point3(0, 0, 0.75),
                    Point3(-7.5, 0, 0.75),
                    Point3(-15, 0, 0.75),
                    Point3(-22.5, 0, 0.75),
                    Point3(-30, 0, 0.75)]

    GameSong = "phase_4/audio/bgm/MG_Dodgeball.ogg"
    GameDesc = ("Welcome to the north! You have been invited to play dodgeball with the penguins!\n\n"
                "How To Play\nWASD to Move and use the mouse to aim.\nLeft click to Throw!\nThrow a "
                "snowball at a teammate to unfreeze them!\n\nThe team with the most points after {0} rounds wins!".format(MaxRounds))

    InitCamTrans = [Point3(25, 45, 19.5317), Vec3(154.001, -15, 0)]

    SnowBallDmg = 25

    GetSnowBalls = "Pick up a snowball from the center!"

    Team2OtherBarrier = {BLUE: "red_barrier_coll", RED: "blue_barrier_coll"}

    def __init__(self, cr):
        try:
            self.DistributedDodgeballGame_initialized
            return
        except:
            self.DistributedDodgeballGame_initialized = 1

        DistributedToonFPSGame.__init__(self, cr)

        TeamMinigame.__init__(self, "BlueSnow", ('phase_4/maps/db_blue_neutral.png',
                                               'phase_4/maps/db_blue_hover.png',
                                               'phase_4/maps/db_blue_hover.png'),
                                    "RedIce", ('phase_4/maps/db_red_neutral.png',
                                               'phase_4/maps/db_red_hover.png',
                                               'phase_4/maps/db_red_hover.png'))

        self.fsm.addState(State('chooseTeam', self.enterChooseTeam, self.exitChooseTeam, ['waitForOthers']))
        self.fsm.addState(State('scrollBy', self.enterScrollBy, self.exitScrollBy, ['countdown']))
        self.fsm.addState(State('countdown', self.enterCountdown, self.exitCountdown, ['play']))
        self.fsm.addState(State('announceGameOver', self.enterAnnGameOver, self.exitAnnGameOver, ['displayWinners', 'countdown']))
        self.fsm.addState(State('displayWinners', self.enterDisplayWinners, self.exitDisplayWinners, ['gameOver']))
        self.fsm.getStateNamed('waitForOthers').addTransition('chooseTeam')
        self.fsm.getStateNamed('waitForOthers').addTransition('scrollBy')
        self.fsm.getStateNamed('play').addTransition('announceGameOver')

        self.firstPerson = DodgeballFirstPerson(self)

        self.scrollBySeq = None
        self.infoText = None

        self.redScoreLbl = None
        self.blueScoreLbl = None

        self.barrierIsStashed = False

        self.mySpawnPoint = 0

        self.infoText = getAlertText()

        self.spawnPointsByTeam = {
            BLUE: [
                [Point3(5, 15, 0), Vec3(180, 0, 0)],
                [Point3(15, 15, 0), Vec3(180, 0, 0)],
                [Point3(-5, 15, 0), Vec3(180, 0, 0)],
                [Point3(-15, 15, 0), Vec3(180, 0, 0)]],
            RED: [
                [Point3(5, -15, 0), Vec3(0, 0, 0)],
                [Point3(15, -15, 0), Vec3(0, 0, 0)],
                [Point3(-5, -15, 0), Vec3(0, 0, 0)],
                [Point3(-15, -15, 0), Vec3(0, 0, 0)]]}

        self.winnerMusic = base.loadMusic('phase_9/audio/bgm/encntr_hall_of_fame.ogg')
        self.loserMusic = base.loadMusic('phase_9/audio/bgm/encntr_sting_announce.ogg')
        self.danceSound = base.loadSfx('phase_3.5/audio/sfx/ENC_Win.ogg')

        # Environment vars
        self.arena = None
        self.olc = None
        self.trees = []
        self.snowballs = []

    def snowballPickupResp(self, flag, idx):
        self.firstPerson.snowballPickupResp(flag, idx)

    def roundOver(self, time = 0):
        teams = [BLUE, RED]
        teams.sort(key = lambda team: self.scoreByTeam[team], reverse = True)
        self.winnerTeam = teams[0]
        base.localAvatar.disableAvatarControls()
        self.firstPerson.end()
        self.deleteTimer()
        self.fsm.request('announceGameOver', [time])

    def getTeamDNAColor(self, team):
        if team == TEAM1:
            return ToonDNA.colorDNA2color['18']
        elif team == TEAM2:
            return ToonDNA.colorDNA2color['02']

    def enterDisplayWinners(self):
        base.localAvatar.stopLookAround()
        base.localAvatar.resetHeadHpr()
        base.localAvatar.getGeomNode().show()
        camera.reparentTo(render)
        camera.setPos((-2.5, 12, 3.5))
        camera.setHpr((-175.074, -5.47218, 0))

        base.transitions.fadeIn()

        base.playSfx(self.danceSound, looping = 1)

        if self.winnerTeam == self.team:
            base.playMusic(self.winnerMusic, volume = 0.8)
        else:
            base.playMusic(self.loserMusic, volume = 0.8)

        winnerPositions = [(-2, 0, 0), (2, 0, 0), (6, 0, 0), (-6, 0, 0)]
        loserPositions = [(-3.5, -10, 0), (-1.5, -15, 0), (3.0, -8, 0), (5.5, -12, 0)]
        for team in [RED, BLUE]:
            for avId in self.playerListByTeam[team]:
                av = self.cr.doId2do.get(avId)
                if av:
                    av.stopSmooth()
                    av.setHpr(0, 0, 0)
                    if team == self.winnerTeam:
                        posList = winnerPositions
                        av.setAnimState("off")
                        av.stop()
                        if not self.getRemoteAvatar(avId).isFrozen:
                            av.loop("win")
                    else:
                        posList = loserPositions
                        av.setAnimState('off')
                        av.stop()
                        if not self.getRemoteAvatar(avId).isFrozen:
                            av.loop("pout")
                    pos = random.choice(posList)
                    posList.remove(pos)
                    av.setPos(pos)

        if self.winnerTeam == self.team:
            text = "YOU WIN!"
        else:
            text = "YOU LOSE!"
        self.gameOverLbl.setText(text)

        self.track = Sequence(
            Wait(2.0),
            Func(self.gameOverLbl.setScale, 0.01),
            Func(self.gameOverLbl.show),
            getAlertPulse(self.gameOverLbl, 0.27, 0.25)
        )
        self.track.start()

        base.localAvatar.collisionsOff()

    def exitDisplayWinners(self):
        base.localAvatar.collisionsOn()
        base.transitions.noTransitions()
        self.danceSound.stop()
        if hasattr(self, 'track'):
            self.track.finish()
            self.track = None
        self.gameOverLbl.hide()

    def __prepareForNextRound(self):
        for av in self.remoteAvatars:
            av.unFreeze()
        pos, hpr = self.spawnPointsByTeam[self.team][self.mySpawnPoint]
        base.localAvatar.setPos(pos)
        base.localAvatar.setHpr(hpr)
        self.playMinigameMusic()
        self.fsm.request('countdown')

    def enterAnnGameOver(self, timeRanOut = 0):
        self.firstPerson.vModel.hide()

        text = getGameText()
        text.setBin('gui-popup', 60)

        ival = Sequence()

        if timeRanOut:
            ival.append(Func(text.setText, "Time's Up!"))
            ival.append(getRoundIval(text))

        ival.append(Func(text.setText, "Round {0} Over!".format(self.getRound())))
        ival.append(getRoundIval(text))

        team = "Red"
        if self.winnerTeam == BLUE:
            team = "Blue"

        if self.round != MaxRounds:
            if self.scoreByTeam[RED] == self.scoreByTeam[BLUE]:
                ival.append(Func(text.setText, "The scores are tied!"))
            else:
                ival.append(Func(text.setText, "{0} is in the lead!".format(team)))
        else:
            ival.append(Func(text.setText, "{0} wins!".format(team)))

        ival.append(getRoundIval(text))
        ival.setDoneEvent(self.uniqueName('annGameOverDone'))
        self.acceptOnce(ival.getDoneEvent(), self.__annGameOverTask)
        self.ival = ival
        self.ival.start()
        self.text = text

        base.transitions.fadeScreen()

    def __annGameOverTask(self):
        if self.round == MaxRounds:
            nextState = Func(self.fsm.request, "displayWinners")
        else:
            nextState = Func(self.__prepareForNextRound)

        self.ival = Sequence(
            base.transitions.getFadeOutIval(),
            nextState
        )
        self.ival.start()

    def exitAnnGameOver(self):
        if hasattr(self, 'ival'):
            self.ignore(self.ival.getDoneEvent())
            self.ival.finish()
            del self.ival
        if hasattr(self, 'text'):
            self.text.destroy()
            del self.text

    def teamWon(self, team, time = 0):
        TeamMinigame.teamWon(self, team, time)
        base.localAvatar.disableAvatarControls()
        self.firstPerson.end()
        self.deleteTimer()
        self.fsm.request('announceGameOver', [time])

    def incrementTeamScore(self, team):
        TeamMinigame.incrementTeamScore(self, team)
        if team == BLUE:
            self.blueScoreLbl.setText("BLUE: " + str(self.scoreByTeam[team]))
            ToontownIntervals.start(ToontownIntervals.getPulseLargerIval(self.blueScoreLbl, 'blueScorePulse'))
        elif team == RED:
            self.redScoreLbl.setText("RED: " + str(self.scoreByTeam[team]))
            ToontownIntervals.start(ToontownIntervals.getPulseLargerIval(self.redScoreLbl, 'redScorePulse'))

    def getWinterDodgeballScoreText(self, color):
        text = OnscreenText(fg = color, font = CIGlobals.getMinnieFont(),
                            scale = 0.15, shadow = (0, 0, 0, 1))
        return text

    def snowballHitWall(self, snowballIndex):
        snowball = self.snowballs[snowballIndex]
        snowball.handleHitWallOrPlayer()
        base.playSfx(snowball.impactSound, node = snowball, volume = 1.5)

    def snowballHitGround(self, snowballIndex):
        snowball = self.snowballs[snowballIndex]
        snowball.handleHitGround()
        base.playSfx(snowball.impactSound, node = snowball, volume = 1.5)

    def snowballHitPlayer(self, damagedPlayer, throwerTeam, snowballIndex):
        av = self.getRemoteAvatar(damagedPlayer)
        if av:
            if throwerTeam == av.team:
                # Someone on my team hit me. Unfreeze me if I am frozen.
                if av.unFreeze():
                    if damagedPlayer == base.localAvatar.doId:
                        self.showAlert("A team member has unfroze you!")
                        self.firstPerson.camFSM.request('unfrozen')
                        self.sendUpdate('teamMateUnfrozeMe', [self.team])
            else:
                # An enemy hit me. Become frozen if I am not already.
                if av.freeze():
                    if damagedPlayer == base.localAvatar.doId:
                        self.showAlert("You've been frozen by an enemy!")
                        self.firstPerson.camFSM.request('frozen')
                        self.sendUpdate('enemyFrozeMe', [self.team, throwerTeam])

        snowball = self.snowballs[snowballIndex]
        snowball.handleHitWallOrPlayer()
        base.playSfx(snowball.impactSound, node = snowball, volume = 1.5)

    def playerCaughtSnowball(self, snowballIndex, catcherId):
        av = self.getRemoteAvatar(catcherId)
        if av:
            snowball = self.snowballs[snowballIndex]
            snowball.pauseThrowIval()
            snowball.pickup(av)

    def setupRemoteAvatar(self, avId):
        av = RemoteDodgeballAvatar(self, self.cr, avId)
        if avId == self.cr.localAvId:
            self.myRemoteAvatar = av
        self.remoteAvatars.append(av)

    def __getSnowTree(self, path):
        trees = loader.loadModel('phase_8/models/props/snow_trees.bam')
        tree = trees.find('**/' + path)
        tree.find('**/*shadow*').removeNode()
        return tree

    def load(self):
        self.setMinigameMusic(DistributedDodgeballGame.GameSong)
        self.setDescription(DistributedDodgeballGame.GameDesc)
        self.setWinnerPrize(200)
        self.setLoserPrize(0)
        self.createWorld()

        self.blueScoreLbl = self.getWinterDodgeballScoreText(VBase4(0, 0, 1, 1))
        self.blueScoreLbl.reparentTo(base.a2dTopLeft)
        self.blueScoreLbl['align'] = TextNode.ALeft
        self.blueScoreLbl.setText('Blue: 0')
        self.blueScoreLbl.setZ(-0.17)
        self.blueScoreLbl.setX(0.05)
        self.blueScoreLbl.hide()

        self.redScoreLbl = self.getWinterDodgeballScoreText(VBase4(1, 0, 0, 1))
        self.redScoreLbl.reparentTo(base.a2dTopLeft)
        self.redScoreLbl['align'] = TextNode.ALeft
        self.redScoreLbl.setText('Red: 0')
        self.redScoreLbl.setZ(-0.35)
        self.redScoreLbl.setX(0.05)
        self.redScoreLbl.hide()

        trans = DistributedDodgeballGame.InitCamTrans
        camera.setPos(trans[0])
        camera.setHpr(trans[1])

        DistributedToonFPSGame.load(self)

    def createWorld(self):
        self.deleteWorld()

        self.arena = loader.loadModel("phase_4/models/minigames/dodgeball_arena.egg")
        self.arena.reparentTo(render)
        self.arena.setScale(0.75)
        self.arena.find('**/team_divider').setBin('ground', 18)
        self.arena.find('**/floor').setBin('ground', 18)
        self.arena.find('**/team_divider_coll').setCollideMask(CIGlobals.FloorBitmask)

        for data in DistributedDodgeballGame.TreeData:
            code = data[0]
            pos = data[1]
            tree = self.__getSnowTree(code)
            tree.reparentTo(self.arena)
            tree.setPos(pos)
            self.trees.append(tree)

        for i in xrange(len(DistributedDodgeballGame.SnowballData)):
            snowdata = DistributedDodgeballGame.SnowballData[i]
            snowball = Snowball(self, i)
            snowball.load()
            snowball.reparentTo(render)
            snowball.setPos(snowdata)
            self.snowballs.append(snowball)

        self.olc = ZoneUtil.getOutdoorLightingConfig(CIGlobals.TheBrrrgh)
        self.olc.setupAndApply()

    def throw(self, snowballIndex, p):
        snowball = self.snowballs[snowballIndex]
        snowball.throw(p)

    def snowballPickup(self, snowballIndex, pickerUpperAvId):
        remoteAv = self.getRemoteAvatar(pickerUpperAvId)
        if remoteAv:
            snowball = self.snowballs[snowballIndex]
            snowball.pickup(remoteAv)

    def deleteWorld(self):
        if self.redScoreLbl:
            self.redScoreLbl.destroy()
            self.redScoreLbl = None
        if self.blueScoreLbl:
            self.blueScoreLbl.destroy()
            self.blueScoreLbl = None
        for snowball in self.snowballs:
            snowball.removeNode()
        self.snowballs = []
        for tree in self.trees:
            tree.removeNode()
        self.trees = []
        if self.olc:
            self.olc.cleanup()
            self.olc = None
        if self.arena:
            self.arena.removeNode()
            self.arena = None
        render.clearFog()

    def enterPlay(self):
        self.createTimer()
        self.redScoreLbl.show()
        self.blueScoreLbl.show()
        self.firstPerson.camFSM.request('unfrozen')

        # Stash the other team's barrier.
        if not self.barrierIsStashed:
            self.arena.find('**/' + self.Team2OtherBarrier[self.team]).stash()
            self.barrierIsStashed = True

    def exitPlay(self):
        self.firstPerson.crosshair.destroy()
        self.firstPerson.crosshair = None
        self.firstPerson.camFSM.request('off')
        DistributedToonFPSGame.exitPlay(self)

    def enterCountdown(self):
        base.transitions.noTransitions()
        self.firstPerson.start()
        self.firstPerson.disableMouse()

        self.setRound(self.getRound() + 1)

        self.infoText.setText(DistributedDodgeballGame.GetSnowBalls)

        self.countdownText = getGameText()
        self.countdownIval = Parallel(
            Sequence(
                Func(self.countdownText.setText, "Round {0}".format(self.getRound())),
                getRoundIval(self.countdownText),
                Func(self.countdownText.setText, "5"),
                getCountdownIval(self.countdownText),
                Func(self.countdownText.setText, "4"),
                getCountdownIval(self.countdownText),
                Func(self.countdownText.setText, "3"),
                getCountdownIval(self.countdownText),
                Func(self.countdownText.setText, "2"),
                getCountdownIval(self.countdownText),
                Func(self.countdownText.setText, "1"),
                getCountdownIval(self.countdownText)),
            getAlertPulse(self.infoText),
            name = "COUNTDOWNIVAL")
        self.countdownIval.setDoneEvent(self.countdownIval.getName())
        self.acceptOnce(self.countdownIval.getDoneEvent(), self.__handleCountdownDone)
        self.countdownIval.start()

    def __handleCountdownDone(self):
        self.fsm.request('play')

    def exitCountdown(self):
        if hasattr(self, 'countdownIval'):
            self.ignore(self.countdownIval.getDoneEvent())
            self.countdownIval.finish()
            del self.countdownIval
        if hasattr(self, 'countdownText'):
            self.countdownText.destroy()
            del self.countdownText

    def enterScrollBy(self):
        BLUE_START_POS = Point3(-20, 0, 4)
        BLUE_END_POS = Point3(20, 0, 4)
        BLUE_HPR = Vec3(0, 0, 0)

        RED_START_POS = Point3(20, 0, 4)
        RED_END_POS = Point3(-20, 0, 4)
        RED_HPR = Vec3(180, 0, 0)

        self.playMinigameMusic()

        self.scrollBySeq = Sequence(
            Func(camera.setHpr, BLUE_HPR),
            LerpPosInterval(
                camera, duration = 5.0, pos = BLUE_END_POS, startPos = BLUE_START_POS, blendType = 'easeOut'),
            Func(base.transitions.fadeOut, 0.4),
            Wait(0.5),
            Func(base.transitions.fadeIn, 0.4),
            Func(camera.setHpr, RED_HPR),
            LerpPosInterval(
                camera, duration = 5.0, pos = RED_END_POS, startPos = RED_START_POS, blendType = 'easeOut'),
            name = "SCROLLBYSEQ")
        self.scrollBySeq.setDoneEvent(self.scrollBySeq.getName())
        self.acceptOnce(self.scrollBySeq.getDoneEvent(), self.__handleScrollByDone)
        self.scrollBySeq.start()

    def __handleScrollByDone(self):
        self.fsm.request('countdown')

    def exitScrollBy(self):
        if self.scrollBySeq:
            self.ignore(self.scrollBySeq.getDoneEvent())
            self.scrollBySeq.finish()
            self.scrollBySeq = None

    def allPlayersReady(self):
        self.fsm.request('scrollBy')

    def chooseUrTeam(self):
        # The AI has told us it's time to choose our team.
        self.fsm.request('chooseTeam')

    def enterChooseTeam(self):
        self.makeSelectionGUI()

    def acceptedIntoTeam(self, spawnPoint):
        TeamMinigame.acceptedIntoTeam(self)

        self.sendUpdate('readyToStart')
        self.fsm.request('waitForOthers')

        self.mySpawnPoint = spawnPoint

        pos, hpr = self.spawnPointsByTeam[self.team][spawnPoint]
        base.localAvatar.setPos(pos)
        base.localAvatar.setHpr(hpr)

    def exitChooseTeam(self):
        self.destroySelectionGUI()

    def announceGenerate(self):
        DistributedToonFPSGame.announceGenerate(self)
        base.camLens.setMinFov(CIGlobals.GunGameFOV / (4./3.))
        self.load()

    def disable(self):
        base.camLens.setMinFov(CIGlobals.DefaultCameraFov / (4./3.))
        self.fsm.requestFinalState()
        self.deleteWorld()
        self.trees = None
        self.snowballs = None
        self.spawnPointsByTeam = None
        if self.firstPerson:
            self.firstPerson.reallyEnd()
            self.firstPerson.cleanup()
            self.firstPerson = None
        self.scrollBySeq = None
        self.winnerMusic = None
        self.loserMusic = None
        self.danceSound = None
        self.infoText = None
        base.localAvatar.setWalkSpeedNormal()
        DistributedToonFPSGame.disable(self)
