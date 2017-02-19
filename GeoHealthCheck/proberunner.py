import sys
import requests
from plugin import Plugin
from factory import Factory
from result import ProbeResult, CheckResult

class ProbeRunner(Plugin):
    """
     Base class for specific implementations to run a Probe with Checks.

    """

    # Generic attributes, subclassses override
    RESOURCE_TYPE = '*'

    # Request attributes, defaults, subclassses override
    REQUEST_METHOD = 'GET'
    REQUEST_HEADERS = None
    REQUEST_TEMPLATE = None

    # Possible response checks attributes, instance determines which
    # checks are selected and their parameters
    RESPONSE_CHECKS = None

    # Lifecycle
    def init(self, probe=None):
        # Probe contains the actual ProbeRunner parameters (from Models/DB) for
        # requests and a list of response Checks with their functions+parameters
        self.probe = probe
        self.response = None
        self.result = None

    # Lifecycle
    def exit(self):
        pass

    def log(self, text):
        print('%s: %s' % (self.__class__.__name__, text))

    def create_result(self):
        """ Create ProbeResult object that gathers all results for single ProbeRunner"""

        self.result = ProbeResult(self)

    def create_check_result(self, check, parameters, success, message):
        """ Create CheckResult object that gathers all results for single Check"""

        return CheckResult(check, parameters, success, message)

    def before_request(self):
        """ Before running actual request to service"""

        self.create_result()

        self.result.start()

    def after_request(self):
        """ After running actual request to service"""

        self.result.stop()

    def perform_request(self):
        """ Perform actual request to service"""

        # Actualize request query string or POST body
        # by substitution in template.
        url_base = self.probe.resource.url

        request_string = None
        if self.REQUEST_TEMPLATE:
            request_string = self.REQUEST_TEMPLATE

            if self.probe.parameters:
                request_parms = self.probe.parameters
                request_string = self.REQUEST_TEMPLATE.format(**request_parms)

        self.log('Doing request: method=%s url=%s' % (self.REQUEST_METHOD, url_base))

        if self.REQUEST_METHOD == 'GET':
            # Default is plain URL, e.g. for WWW:LINK
            url = url_base
            if request_string:
                # Query String: mainly OWS:* resources
                url = "%s%s" % (url, request_string)
                
            self.response = requests.get(url,
                                         headers=self.REQUEST_HEADERS)
        elif self.REQUEST_METHOD == 'POST':
            self.response = requests.post(url_base,
                                          data=request_string,
                                          headers=self.REQUEST_HEADERS)

        self.log('response: status=%d' % (self.response.status_code))
        if self.response.status_code /100 in [4,5]:
            self.log('Errro response: %s' % (str(self.response.text)))


    def run_request(self):
        """ Run actual request to service"""
        self.before_request()
        self.perform_request()
        self.after_request()

    def run_checks(self):
        """ Do the checks on the response from request"""

        # Config also determines which actual checks are performed from possible
        # Checks in ProbeRunner. Checks are performed by Checker instances.
        checks = self.probe.checks
        for check in checks:
            checker_class = check.checker
            checker = Factory.create_obj(checker_class)
            try:
                checker.init(self, check.parameters)
                result = checker.perform()
            except:
                msg = "Exception: %s" % str(sys.exc_info())
                self.log(msg)
                result = False, msg
            self.log('Check: fun=%s result=%s' % (checker_class, result[0]))

            self.result.add_result(self.create_check_result(
                check, check.parameters, result[0], result[1]))
     # Lifecycle
    def calc_result(self):
        """ Calculate overall result from the Result object"""
        self.log("Result: %s" % str(self.result))

    @staticmethod
    def run(probe):
        """ Class method to create and run a single ProbeRunner"""

        # Create ProbeRunner instance from module.class string
        proberunner = Factory.create_obj(probe.proberunner)

        # Initialize with actual parameters
        proberunner.init(probe)

        # Perform request
        proberunner.run_request()

        # Perform the ProbeRunner's checks
        proberunner.run_checks()

        # Determine result
        proberunner.calc_result()

        # Lifecycle
        proberunner.exit()

        # Return result
        return proberunner.result

