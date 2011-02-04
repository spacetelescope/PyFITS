import warnings


class VerifyError(Exception):
    """
    Verify exception class.
    """
    pass


class _Verify(object):
    """
    Shared methods for verification.
    """

    def run_option(self, option="warn", err_text="", fix_text="Fixed.", fix = "pass", fixable=1):
        """
        Execute the verification with selected option.
        """
        _text = err_text
        if not fixable:
            option = 'unfixable'
        if option in ['warn', 'exception']:
            #raise VerifyError, _text
        #elif option == 'warn':
            pass

        # fix the value
        elif option == 'unfixable':
            _text = "Unfixable error: %s" % _text
        else:
            exec(fix)
            #if option != 'silentfix':
            _text += '  ' + fix_text
        return _text

    def verify(self, option='warn'):
        """
        Verify all values in the instance.

        Parameters
        ----------
        option : str
            Output verification option.  Must be one of ``"fix"``,
            ``"silentfix"``, ``"ignore"``, ``"warn"``, or
            ``"exception"``.  See :ref:`verify` for more info.
        """

        _option = option.lower()
        if _option not in ['fix', 'silentfix', 'ignore', 'warn', 'exception']:
            raise ValueError, 'Option %s not recognized.' % option

        if (_option == "ignore"):
            return

        x = str(self._verify(_option)).rstrip()
        if _option in ['fix', 'silentfix'] and x.find('Unfixable') != -1:
            raise VerifyError, '\n'+x
        if (_option != "silentfix"and _option != 'exception') and x:
            warnings.warn('Output verification result:')
            warnings.warn(x)
        if _option == 'exception' and x:
            raise VerifyError, '\n'+x


