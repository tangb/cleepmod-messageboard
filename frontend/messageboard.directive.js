/**
 * Message board config directive
 */
var messageboardDirective = function($rootScope, raspiotService, toast, messageboardService, confirm, $mdDialog) {

    var messageboardController = ['$scope', function($scope) {
        var self = this;
        self.message = '';
        self.startDate = moment().toDate();
        self.startTime = moment().format('HH:mm');
        self.endDate = moment().add(2, 'hours').toDate();
        self.endTime = moment().add(2, 'hours').format('HH:mm');
        self.messages = [];
        self.duration = 30;
        self.speed = 0.005;
        self.boardIsOn = true;

        /**
         * Cancel dialog
         */
        self.cancelDialog = function() {
            $mdDialog.cancel();
        };

        /**
         * Close dialog
         */
        self.closeDialog = function() {
            //check values
            if( self.message.length===0 || self.startDate.length===0 || self.startTime.length===0 || self.endDate.length===0 || self.endTime.length===0 )
            {
                toast.error('All fields are required');
            }
            else
            {
                $mdDialog.hide();
            }
        };

        /**
         * Reset editor's values
         */
        self._resetValues = function() {
            self.message = '';
            self.startDate = moment().toDate();
            self.endDate = moment().add(2, 'hours').toDate();
            self.startTime = moment().format('HH:mm');
            self.endTime = moment().add(2, 'hours').format('HH:mm');
        };

        /**
         * Open add dialog (internal use)
         */
        self._openAddDialog = function() {
            return $mdDialog.show({
                controller: function() { return self; },
                controllerAs: 'boardCtl',
                templateUrl: 'addMessage.directive.html',
                parent: angular.element(document.body),
                clickOutsideToClose: false,
                fullscreen: true
            });
        };
        
        /**
         * Add message
         */
        self.openAddDialog = function() {
            //reset values
            self._resetValues();

            self._openAddDialog()
                .then(function() {
                    return self.addMessage();
                })
                .then(function() {
                    return raspiotService.reloadModuleConfig('messageboard');
                })
                .then(function(config) {
                    self.messages = config.messages;
                    toast.success('Message added');
                });
        }; 

        /**
         * Add message
         */
        self.addMessage = function() {
            //prepare data
            var temp = self.startTime.split(':');
            var start = moment(self.startDate).hours(temp[0]).minutes(temp[1]);
            temp = self.endTime.split(':');
            var end = moment(self.endDate).hours(temp[0]).minutes(temp[1]);

            return messageboardService.addMessage(self.message, start.unix(), end.unix());
        };

        /**
         * Delete message
         */
        self.deleteMessage = function(message) {
            confirm.open('Delete message ?', 'Message will be lost', 'Delete')
                .then(function() {
                    return messageboardService.deleteMessage(message.uuid);
                })
                .then(function(resp) {
                    return raspiotService.reloadModuleConfig('messageboard');
                })
                .then(function(config) {
                    self.messages = config.messages;
                    toast.success('Message deleted');
                }); 
        };

        /**
         * Save configuration
         */
        self.saveConfiguration = function() {
            messageboardService.saveConfiguration(self.duration, self.speed)
                .then(function(resp) {
                    toast.success('Configuration saved');
                });
        };

        /**
         * Turn on/off board
         */
        self.turnOff = function() {
            if( !self.boardIsOn )
            {
                messageboardService.turnOff();
            }
            else
            {
                messageboardService.turnOn();
            }
        };

        /**
         * Init controller
         */
        self.init = function() {
            raspiotService.getModuleConfig('messageboard')
                .then(function(config) {
                    self.duration = config.duration;
                    self.speed = config.speed;
                    self.boardIsOn = !config.status.off;
                    self.messages = config.messages;
                });

            //add module actions to fabButton
            var actions = [{
                icon: 'plus',
                callback: self.openAddDialog,
                tooltip: 'Add message'
            }]; 
            $rootScope.$broadcast('enableFab', actions);
        };
    }];

    var messageboardLink = function(scope, element, attrs, controller) {
        controller.init();
    };

    return {
        templateUrl: 'messageboard.directive.html',
        replace: true,
        scope: true,
        controller: messageboardController,
        controllerAs: 'boardCtl',
        link: messageboardLink
    };
};

var RaspIot = angular.module('RaspIot');
RaspIot.directive('messageboardConfigDirective', ['$rootScope', 'raspiotService', 'toastService', 'messageboardService', 'confirmService', '$mdDialog', messageboardDirective]);

