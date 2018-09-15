#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
from raspiot.raspiot import RaspIotRenderer
import time
from raspiot.libs.internals.task import BackgroundTask
from raspiot.libs.drivers.ht1632c import HT1632C
from raspiot.utils import InvalidParameter, MissingParameter
from raspiot.profiles import DisplayLimitedTimeMessageProfile, DisplayAddOrReplaceMessageProfile
import uuid
import socket

__all__ = ['Messageboard']

class Message():
    """
    Messageboard Message object
    """
    def __init__(self, message=None, start=None, end=None):
        self.message = message
        self.start = start
        self.end = end
        self.displayed_time = 0
        self.dynamic = False
        self.uuid = unicode(uuid.uuid4())

    def from_dict(self, message):
        """
        Load message from dict
        """
        self.message = message[u'message']
        self.start = message[u'start']
        self.end = message[u'end']
        self.uuid = message[u'uuid']

    def to_dict(self):
        """
        Return message as dict
        """
        return {
            u'uuid': self.uuid,
            u'message': self.message,
            u'start': self.start,
            u'end': self.end,
            u'displayed_time': self.displayed_time
        }

    def __str__(self):
        return u'Message "%s" [%d:%d] %d' % (self.message, self.start, self.end, self.displayed_time)




class Messageboard(RaspIotRenderer):
    """
    Messageboard allows user to display message on single line board
    Icons are directly handled inside message
    """
    MODULE_AUTHOR = u'Cleep'
    MODULE_VERSION = u'1.0.0'
    MODULE_PRICE = 0
    MODULE_DEPS = []
    MODULE_DESCRIPTION = u'Displays your own infos on a single line LED panel.'
    MODULE_LOCKED = False
    MODULE_TAGS = [u'display', u'led']
    MODULE_COUNTRY = None
    MODULE_URLINFO = None
    MODULE_URLHELP = None
    MODULE_URLINFO = None
    MODULE_URLBUGS = None

    MODULE_CONFIG_FILE = u'messageboard.conf'
    DEFAULT_CONFIG = {
        u'duration': 60,
        u'messages' : [],
        u'speed': 'normal'
    }

    RENDERER_PROFILES = [DisplayLimitedTimeMessageProfile, DisplayAddOrReplaceMessageProfile]
    RENDERER_TYPE = u'display'

    SPEED_SLOW = u'slow'
    SPEED_NORMAL = u'normal'
    SPEED_FAST = u'fast'
    SPEEDS = {
        SPEED_SLOW: 0.0025,
        SPEED_NORMAL: 0.005,
        SPEED_FAST: 0.0075
    }

    def __init__(self, bootstrap, debug_enabled):
        """
        Constructor

        Args:
            bootstrap (dict): bootstrap objects
            debug_enabled (bool): flag to set debug level to logger
        """
        #init
        RaspIotRenderer.__init__(self, bootstrap, debug_enabled)

        #members
        self.__current_message = None
        self.messages = []

        #init board
        pin_a0 = 15
        pin_a1 = 16
        pin_a2 = 18
        pin_e3 = 22
        panels = 4
        self.board = HT1632C(pin_a0, pin_a1, pin_a2, pin_e3, panels)
        self.__set_board_units()
        self.board.set_scroll_speed(self.SPEEDS[self._get_config_field(u'speed')])
        self.__display_task = None

        #events
        self.messageboardMessageUpdate = self._get_event('messageboard.message.update')

    def _configure(self):
        """
        Configure module
        """
        #load messages
        for msg in self._get_config_field(u'messages'):
            message = Message()
            message.from_dict(msg)
            self.messages.append(message)

        #create device if necessary
        if self._get_device_count()==0:
            #add default device to get a valid uuid
            self._add_device({
                u'name': u'MessageBoard',
                u'type': u'messageboard'
            })

        #init display task
        self.__display_task = BackgroundTask(self.__display_message, self.logger, float(self._get_config_field(u'duration')))
        self.__display_task.start()

        #display ip at startup during 1 minute
        #@see http://stackoverflow.com/a/1267524
        #ip = [l for l in ([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")][:1], [[(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) if l][0][0]
        #now = int(time.time())
        #self.add_message(u'IP: %s' % unicode(ip), now, now+60)

    def _stop(self):
        """
        Stop module
        """
        #clean board
        self.board.cleanup()

        #stop task
        if self.__display_task:
            self.__display_task.stop()

    def __display_message(self):
        """
        Display messages. Called every seconds by task
        """
        try:
            #now
            now = time.time()
            self.logger.debug(u'__display_message at %d' % now)

            #get messages to display
            messages_to_display = []
            for msg in self.messages[:]:
                if now>=msg.start and now<=msg.end:
                    #this message could be displayed
                    messages_to_display.append(msg)

                elif now>msg.end:
                    self.logger.debug(u'Remove obsolete message %s' % unicode(msg))
                    #remove obsolete message from config
                    config = self._get_config()
                    messages = self._get_config_field(u'messages')
                    for msg_conf in messages:
                        if msg_conf[u'uuid']==msg.uuid:
                            messages.remove(msg_conf)
                            self._set_config_field(u'messages', messages)
                            break

                    #remove message internaly
                    self.messages.remove(msg)

            #sort messages to display by date
            #msg's displayed_time is set when message is displayed
            #message not displayed yet has displayed_time set to 0
            #so naturally oldest messages or not already displayed are sorted at top of list
            messages_to_display.sort(key=lambda msg:msg.displayed_time, reverse=False)

            if self.logger.getEffectiveLevel()==logging.DEBUG:
                self.logger.debug(u'Messages to display:')
                for msg in messages_to_display:
                    self.logger.debug(u' - %s' % unicode(msg))

            #display first list message
            if len(messages_to_display)>0:
                #get first list message
                msg = messages_to_display[0]
                if msg!=self.__current_message or msg.dynamic==True:
                    self.logger.debug(u' ==> Display message %s' % unicode(msg))
                    msg.dynamic = self.board.display_message(msg.message)
                    msg.displayed_time = now
                    self.__current_message = msg

                    #push event
                    self.messageboardMessageUpdate.send(params=self.get_current_message())

            else:
                #no message to display, clear screen
                self.__current_message = None
                self.board.clear()

        except:
            self.logger.exception(u'Exception on message displaying:')

    def get_module_config(self):
        """
        Return module full configuration

        Returns:
            dict: module configuration::
                {
                    messages (list): list of displayed messages
                    duration (float): message duration
                    speed (int): scroll speed
                    status (dict): current message data
                }
        """
        config = self._get_config()

        out = {}
        out[u'messages'] = self.get_messages()
        out[u'duration'] = config[u'duration']
        out[u'speed'] = config[u'speed']
        out[u'status'] = self.get_current_message()

        return out;

    def get_module_devices(self):
        """
        Return updated messageboard device

        Returns:
            dict: current message data
        """
        devices = super(Messageboard, self).get_module_devices()
        uuid = devices.keys()[0]
        data = self.get_current_message()
        devices[uuid].update(data)

        return devices

    def __set_board_units(self):
        """
        Set board units
        """
        #set board unit
        self.board.set_time_units(u'minutes', u'hours', u'days')

    def _render(self, profile):
        """
        Render message to screen

        Args:
            profile (any profile): profile to display
        """
        if isinstance(profile, DisplayAddOrReplaceMessageProfile):
            #replace (or add) message using specified uuid
            self.add_or_replace_message(profile.message, profile.uuid)

        elif isinstance(profile, DisplayLimitedTimeMessageProfile):
            #add message
            self.add_message(profile.message, profile.start, profile.end)

    def add_message(self, message, start, end):
        """
        Add message to display

        Params:
            message (string): message to display
            start (timestamp): date to start displaying message from
            end (timestamp): date to stop displaying message
        
        Returns:
            string: message uuid
        """
        #create message object
        msg = Message(message, start, end)
        self.logger.debug(u'Add new message: %s' % unicode(msg))

        #save it to config
        messages = self._get_config_field(u'messages')
        messages.append(msg.to_dict())
        self._set_config_field(u'messages', messages)

        #save it to internaly
        self.messages.append(msg)
        
        return msg.uuid

    def delete_message(self, uuid):
        """
        Delete specified message

        Params:
            uuid (string): message uuid

        Returns:
            bool: True if message deleted
        """
        deleted = False

        #delete message from config
        messages = self._get_config_field(u'messages')
        for msg in messages:
            if msg[u'uuid']==uuid:
                messages.remove(msg)
                deleted = True
                break
        if deleted:
            self._set_config_field(u'messages', messages)

        #and delete it internaly
        for msg in self.messages[:]:
            if msg.uuid==uuid:
                self.messages.remove(msg)
                break

        self.logger.debug(u'Message "%s" deleted' % msg.message)

        return deleted

    def add_or_replace_message(self, message, uuid):
        """
        Add or replace unlimited (1 week in reality) message by new specified infos.
        Useful to cycle message.
        
        Params:
            message (string): message to display
            uuid (string): message uuid to replace

        Returns:
            bool: True if message replaced
        """
        self.logger.debug(u'Replacing message uuid "%s" with message "%s"' % (uuid, message))
        #replace message in config
        replaced = False
        messages = self._get_config_field(u'messages')
        start = int(time.time())
        end = start + 604800 #1 week
        for msg in messages:
            if msg[u'uuid']==uuid:
                #message found, replace infos by new ones
                msg[u'message'] = message
                msg[u'start'] = start
                msg[u'end'] = end
                replaced = True
                break

        if replaced:
            #message found and replaced
            self.logger.debug(u'Message replaced')
            self._set_config_field(u'messages', messages)

            #replace message internaly
            for msg in self.messages:
                if msg.uuid==uuid:
                    msg.message = message
                    msg.start = start
                    msg.end = end

                    #force message to be displayed again
                    self.__current_message = None

        else:
            #message not found
            self.logger.debug(u'Message added instead of replaced')
            
            #create message object
            msg = Message(message, start, end)
            msg.uuid = uuid

            #save it to config
            messages = self._get_config_field(u'messages')
            messages.append(msg.to_dict())
            self._set_config_field(u'messages', messages)

            #save it to internaly
            self.messages.append(msg)

        return replaced

    def get_messages(self):
        """
        Return all messages

        Returns:
            list: list of messages
        """
        msgs = []
        for msg in self.messages:
            msgs.append(msg.to_dict())

        return msgs

    def get_current_message(self):
        """
        Return current displayed message

        Returns:
            dict: current message data::
                {
                    nomessage (bool): True if no message displayed
                    off (bool): True if board is off
                    message (string): current message
                }
        """
        out = {
            u'nomessage': False,
            u'off': False,
            u'message': None
        }

        if self.__current_message is None:
            #no message displayed for now, return empty string
            out[u'nomessage'] = True
        elif not self.board.is_on():
            #board is off
            out[u'off'] = True
        else:
            #send message
            out[u'message'] = self.__current_message.to_dict()

        return out

    def turn_on(self):
        """
        Turn on board
        """
        #just turn on display
        self.board.turn_on()

        #set current message to None to force current message to be displayed again
        self.__current_message = None

        #push event
        self.messageboardMessageUpdate(params=self.get_current_message())

    def turn_off(self):
        """
        Turn off board
        """
        #clear board first
        self.board.clear()

        #and turn off display
        self.board.turn_off()

        #push event
        self.messageboardMessageUpdate(params=self.get_current_message())

    def is_on(self):
        """
        Return board status (on/off)

        Returns:
            bool: True if board is on, False otherwise
        """
        return self.board.is_on()

    def save_configuration(self, duration, speed):
        """
        Save board configuration

        Args:
            duration (float): message duration (cycling time)
            speed (slow|normal|fast): message scrolling speed

        Raises:
            InvalidParameter, MissingParameter
        """
        if duration is None:
            raise MissingParameter(u'Duration parameter is missing')
        if duration<5 or duration>60:
            raise InvalidParameter(u'Duration value must be between 5 and 60 seconds')
        if speed is None or len(speed)==0:
            raise MissingParameter(u'Speed parameter is missing')
        if speed not in self.SPEEDS:
            raise InvalidParameter(u'Speed value is not valid')

        #save config
        self._update_config({
            u'duration': float(duration),
            u'speed': speed
        })

        #update board configuration
        self.board.set_scroll_speed(self.SPEEDS[speed])

        #stop current task
        if self.__display_task:
            self.__display_task.stop()
        
        #and restart new one
        self.__display_task = BackgroundTask(self.__display_message, self.logger, float(duration))
        self.__display_task.start()



if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(name)s %(levelname)s : %(message)s")
    board = Messageboard()
    now = int(time.time())
    now_15 = now + 15
    now_30 = now + 30
    now_45 = now + 45
    now_60 = now + 60
    board.add_message('msg0', now, now_15+60, False)
    board.add_message('msg1', now_15, now_15+30, False)
    board.add_message('msg2', now_30, now_30+45, False)
    board.add_message('msg3', now_45, now_45+30, False)
    board.add_message('msg4', now_60, now_60+30, False)
    try:
        while True:
            time.sleep(0.25)
    except:
        pass

    board.stop()
