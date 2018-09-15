/**
 * MessageBoard service
 * Handle messageboard module requests
 */
var messageboardService = function($q, $rootScope, rpcService, raspiotService) {
    var self = this;
    
    /**
     * Add new message
     */
    self.addMessage = function(message, start, end) {
        return rpcService.sendCommand('add_message', 'messageboard', {'message':message, 'start':start, 'end':end});
    };

    /**
     * Delete message
     */
    self.deleteMessage = function(uuid) {
        return rpcService.sendCommand('delete_message', 'messageboard', {'uuid':uuid});
    };

    /**
     * Get messages
     */
    self.getMessages = function() {
        return rpcService.sendCommand('get_messages', 'messageboard');
    };

    /**
     * Save board configuration
     */
    self.saveConfiguration = function(duration, speed) {
        return rpcService.sendCommand('save_configuration', 'messageboard', {speed:speed, duration:duration});
    };

    /**
     * Turn off board
     */
    self.turnOff = function() {
        return rpcService.sendCommand('turn_off', 'messageboard');
    };

    /**
     * Turn on board
     */
    self.turnOn = function() {
        return rpcService.sendCommand('turn_on', 'messageboard');
    };

    /**
     * Get board status (on/off)
     */
    self.isOn = function() {
        return rpcService.sendCommand('is_on', 'messageboard');
    };

    /**
     * Catch message updated
     */
    $rootScope.$on('messageboard.message.update', function(event, uuid, params) {
        for( var i=0; i<raspiotService.devices.length; i++ )
        {
            if( raspiotService.devices[i].uuid==uuid )
            {
                var message = self._formatMessageData(params);
                raspiotService.devices[i].message = message.message;
                raspiotService.devices[i].lastupdate = message.lastupdate;
            }
        }
    });

};
    
var RaspIot = angular.module('RaspIot');
RaspIot.service('messageboardService', ['$q', '$rootScope', 'rpcService', 'raspiotService', messageboardService]);

