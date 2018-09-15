/**
 * Messageboard widget directive
 * Display messageboard dashboard widget
 */
var widgetMessageboardDirective = function() {

    var widgetMessageboardController = ['$scope', function($scope) {
        var self = this;
        self.device = $scope.device;
    }];

    return {
        restrict: 'EA',
        templateUrl: 'messageboard.widget.html',
        replace: true,
        scope: {
            'device': '='
        },
        controller: widgetMessageboardController,
        controllerAs: 'widgetCtl'
    };
};

var RaspIot = angular.module('RaspIot');
RaspIot.directive('widgetMessageboardDirective', [widgetMessageboardDirective]);

