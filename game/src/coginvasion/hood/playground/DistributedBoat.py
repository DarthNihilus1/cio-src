"""
COG INVASION ONLINE
Copyright (c) CIO Team. All rights reserved.

@file DistributedBoat.py
@author Brian Lach
@date July 26, 2015

"""

from direct.directnotify.DirectNotifyGlobal import directNotify
from direct.distributed.DistributedObject import DistributedObject
from direct.distributed.ClockDelta import globalClockDelta
from direct.fsm.State import State
from direct.fsm.ClassicFSM import ClassicFSM
from direct.directutil import Mopath
from direct.interval.IntervalGlobal import MopathInterval, Parallel, LerpQuatInterval, SoundInterval, Sequence, Wait

from panda3d.core import CollisionSphere, CollisionNode 

from src.coginvasion.globals import CIGlobals
from src.coginvasion.holiday.HolidayManager import HolidayType

class DistributedBoat(DistributedObject):
    notify = directNotify.newCategory("DistributedBoat")

    def __init__(self, cr):
        DistributedObject.__init__(self, cr)
        self.fsm = ClassicFSM(
            'DistributedBoat',
            [
                State('off', self.enterOff, self.exitOff),
                State('eastToWest', self.enterEastToWest, self.exitEastToWest),
                State('westToEast', self.enterWestToEast, self.exitWestToEast)
            ],
            'off', 'off'
        )
        self.boat = None
        self.eastPier = None
        self.eastPierPath = 'east_pier'
        self.westPier = None
        self.westPierPath = 'west_pier'
        self.pierUpP = 0.0
        self.pierDownP = -45.0
        self.fogHorn = 'phase_5/audio/sfx/SZ_DD_foghorn.ogg'
        self.shipBell = 'phase_6/audio/sfx/SZ_DD_shipbell.ogg'
        self.waterLap = 'phase_6/audio/sfx/SZ_DD_waterlap.ogg'
        self.dockCreak = 'phase_6/audio/sfx/SZ_DD_dockcreak.ogg'
        self.eastWest = 'phase_6/paths/dd-e-w.bam'
        self.westEast = 'phase_6/paths/dd-w-e.bam'
        self.boatPath = '*donalds_boat*'
        self.track = None
        self.state = None
        
        # Variables that handle the winter collision node.
        self.crashColl = None
        self.crashCollNP = None

    def __handleOnBoat(self, entry):
        base.localAvatar.b_setParent(CIGlobals.SPDonaldsBoat)
        base.playSfx(self.soundWaterLap, looping = 1)

    def __handleOffBoat(self, entry):
        base.localAvatar.b_setParent(CIGlobals.SPRender)
        self.soundWaterLap.stop()

    def __pollBoat(self, task):
        try:
            self.boat = self.cr.playGame.hood.loader.geom.find('**/' + self.boatPath)
        except:
            return task.cont
        self.generated()
        return task.done

    def generate(self):
        DistributedObject.generate(self)
        self.soundFogHorn = base.loadSfx(self.fogHorn)
        self.soundShipBell = base.loadSfx(self.shipBell)
        self.soundWaterLap = base.loadSfx(self.waterLap)
        self.soundDockCreak = base.loadSfx(self.dockCreak)
        #try:
        #    self.boat = self.cr.playGame.hood.loader.geom.find('**/' + self.boatPath)
        #except:
    #        base.taskMgr.add(self.__pollBoat, self.uniqueName('__pollBoat'))
    #        return
        self.boat = self.cr.playGame.hood.loader.geom.find('**/' + self.boatPath)
        self.boat.setMaterial(CIGlobals.getShinyMaterial())
        self.generated()

    def generated(self):
        self.eastPier = self.cr.playGame.hood.loader.geom.find('**/' + self.eastPierPath)
        self.westPier = self.cr.playGame.hood.loader.geom.find('**/' + self.westPierPath)
        base.cr.parentMgr.registerParent(CIGlobals.SPDonaldsBoat, self.boat)
        self.accept('enterdonalds_boat_floor', self.__handleOnBoat)
        self.accept('exitdonalds_boat_floor', self.__handleOffBoat)
        self.d_requestCurrentStateAndTimestamp()
        self.fsm.enterInitialState()
        
        if base.cr.holidayManager.getHoliday() == HolidayType.CHRISTMAS:
            self.boat.setPosHpr(12.73, -1.6, -4.7, 341.57, 350.0, 26.5)
            self.fsm.request('off')
            
            self.crashColl = CollisionSphere(0, 0, 0, 15)
            self.crashCollNP = self.boat.attachNewNode(CollisionNode('crashed_boat_collision'))
            self.crashCollNP.node().addSolid(self.crashColl)
            self.crashCollNP.node().setCollideMask(CIGlobals.WallBitmask)
            self.crashCollNP.setSz(2)
            self.crashCollNP.setSx(0.75)
            self.crashCollNP.setSy(1.25)
            self.crashCollNP.setPosHpr(2.05, 3.21, 1.66, 8.44, 6.93, 332.61)

    def disable(self):
        base.taskMgr.remove(self.uniqueName('__pollBoat'))
        base.cr.parentMgr.unregisterParent(CIGlobals.SPDonaldsBoat)
        self.ignore('enterdonalds_boat_floor')
        self.ignore('exitdonalds_boat_floor')
        self.fsm.requestFinalState()
        
        if self.crashCollNP:
            self.crashCollNP.removeNode()
            del self.crashCollNP
            del self.crashColl
        
        del self.fsm
        del self.soundFogHorn
        del self.soundShipBell
        del self.soundWaterLap
        del self.soundDockCreak
        self.fogHorn = None
        self.shipBell = None
        self.waterLap = None
        self.dockCreak = None
        self.boat = None
        self.track = None
        self.pierDownP = None
        self.pierUpP = None
        self.eastPier = None
        self.eastPierPath = None
        self.westPier = None
        self.westPierPath = None
        self.boatPath = None
        self.westEast = None
        self.eastWest = None
        DistributedObject.disable(self)

    def currentStateAndTimestamp(self, state, timestamp):
        self.setState(state, timestamp)

    def d_requestCurrentStateAndTimestamp(self):
        self.sendUpdate('requestCurrentStateAndTimestamp', [])

    def setState(self, state, timestamp = None):
        if timestamp is None:
            ts = 0.0
        else:
            ts = globalClockDelta.localElapsedTime(timestamp)
        self.state = state
        if self.boat and base.cr.holidayManager.getHoliday() != HolidayType.CHRISTMAS:
            self.fsm.request(state, [ts])

    def enterEastToWest(self, ts = 0):
        moPath = Mopath.Mopath()
        moPath.loadFile(self.eastWest)
        moIval = MopathInterval(moPath, self.boat)

        self.track = Parallel(
            SoundInterval(self.soundShipBell, node = self.boat),
            SoundInterval(self.soundDockCreak, node = self.eastPier),
            moIval,
            LerpQuatInterval(
                self.eastPier,
                duration = 5.0,
                quat = (90, self.pierDownP, 0),
                startHpr = (90, self.pierUpP, 0)
            ),
            Sequence(
                Wait(15.0),
                Parallel(
                    LerpQuatInterval(
                        self.westPier,
                        duration = 5.0,
                        quat = (-90, self.pierUpP, 0),
                        startHpr = (-90, self.pierDownP, 0)
                    ),
                    Sequence(
                        Wait(2.0),
                        SoundInterval(self.soundDockCreak, node = self.westPier)
                    )
                ),
                SoundInterval(self.soundFogHorn, node = self.boat)
            )
        )
        self.track.start(ts)

    def exitEastToWest(self):
        if self.track:
            self.track.finish()
            self.track = None

    def enterWestToEast(self, ts = 0):
        moPath = Mopath.Mopath()
        moPath.loadFile(self.westEast)
        moIval = MopathInterval(moPath, self.boat)

        self.track = Parallel(
            SoundInterval(self.soundShipBell, node = self.boat),
            SoundInterval(self.soundDockCreak, node = self.westPier),
            moIval,
            LerpQuatInterval(
                self.westPier,
                duration = 5.0,
                quat = (-90, self.pierDownP, 0),
                startHpr = (-90, self.pierUpP, 0)
            ),
            Sequence(
                Wait(15.0),
                Parallel(
                    LerpQuatInterval(
                        self.eastPier,
                        duration = 5.0,
                        quat = (90, self.pierUpP, 0),
                        startHpr = (90, self.pierDownP, 0)
                    ),
                    Sequence(
                        Wait(2.0),
                        SoundInterval(self.soundDockCreak, node = self.eastPier)
                    )
                ),
                SoundInterval(self.soundFogHorn, node = self.boat)
            )
        )
        self.track.start(ts)

    def exitWestToEast(self):
        if self.track:
            self.track.finish()
            self.track = None

    def enterOff(self):
        pass

    def exitOff(self):
        pass
