"""
PC-BASIC - functions.py
BASIC functions.

(c) 2013, 2014, 2015, 2016 Rob Hagemans
This file is released under the GNU GPL version 3 or later.
"""

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO
from functools import partial
import logging

from . import fp
from . import values
from . import shell
from . import util
from . import error
from . import basictoken as tk


class Functions(object):
    """BASIC functions."""

    def __init__(self, parser):
        """Initialise function context."""
        self.parser = parser
        self.session = parser.session
        self.values = self.session.values
        # state variable for detecting recursion
        self.user_function_parsing = set()
        self._init_functions()

    def _init_functions(self):
        """Initialise functions."""
        self.functions = {
            tk.INPUT: self.value_input,
            tk.SCREEN: self.value_screen,
            tk.USR: self.value_usr,
            tk.FN: self.value_fn,
            tk.ERL: self.value_erl,
            tk.ERR: self.value_err,
            tk.STRING: self.value_string,
            tk.INSTR: self.value_instr,
            tk.VARPTR: self.value_varptr,
            tk.CSRLIN: self.value_csrlin,
            tk.POINT: self.value_point,
            tk.INKEY: self.value_inkey,
            tk.CVI: partial(self.value_func, fn=self.values.cvi),
            tk.CVS: partial(self.value_func, fn=self.values.cvs),
            tk.CVD: partial(self.value_func, fn=self.values.cvd),
            tk.MKI: partial(self.value_func, fn=self.values.mki),
            tk.MKS: partial(self.value_func, fn=self.values.mks),
            tk.MKD: partial(self.value_func, fn=self.values.mkd),
            tk.EXTERR: self.value_exterr,
            tk.DATE: self.value_date,
            tk.TIME: self.value_time,
            tk.PLAY: self.value_play,
            tk.TIMER: self.value_timer,
            tk.ERDEV: self.value_erdev,
            tk.IOCTL: self.value_ioctl,
            tk.ENVIRON: self.value_environ,
            tk.PMAP: self.value_pmap,
            tk.LEFT: self.value_left,
            tk.RIGHT: self.value_right,
            tk.MID: self.value_mid,
            tk.SGN: partial(self.value_func, fn=self.values.sgn),
            tk.INT: partial(self.value_func, fn=self.values.floor),
            tk.ABS: partial(self.value_func, fn=self.values.abs),
            tk.SQR: partial(self.value_func, fn=self.values.sqr),
            tk.RND: self.value_rnd,
            tk.SIN: partial(self.value_func, fn=self.values.sin),
            tk.LOG: partial(self.value_func, fn=self.values.log),
            tk.EXP: partial(self.value_func, fn=self.values.exp),
            tk.COS: partial(self.value_func, fn=self.values.cos),
            tk.TAN: partial(self.value_func, fn=self.values.tan),
            tk.ATN: partial(self.value_func, fn=self.values.atn),
            tk.FRE: self.value_fre,
            tk.INP: self.value_inp,
            tk.POS: self.value_pos,
            tk.LEN: partial(self.value_func, fn=self.values.length),
            tk.STR: partial(self.value_func, fn=self.values.representation),
            tk.VAL: partial(self.value_func, fn=self.values.val),
            tk.ASC: partial(self.value_func, fn=self.values.asc),
            tk.CHR: partial(self.value_func, fn=self.values.character),
            tk.PEEK: self.value_peek,
            tk.SPACE: partial(self.value_func, fn=self.values.space),
            tk.OCT: partial(self.value_func, fn=self.values.octal),
            tk.HEX: partial(self.value_func, fn=self.values.hexadecimal),
            tk.LPOS: self.value_lpos,
            tk.CINT: partial(self.value_func, fn=values.pass_integer),
            tk.CSNG: partial(self.value_func, fn=self.values.pass_single),
            tk.CDBL: partial(self.value_func, fn=self.values.pass_double),
            tk.FIX: partial(self.value_func, fn=self.values.fix),
            tk.PEN: self.value_pen,
            tk.STICK: self.value_stick,
            tk.STRIG: self.value_strig,
            tk.EOF: self.value_eof,
            tk.LOC: self.value_loc,
            tk.LOF: self.value_lof,
        }

    def __getstate__(self):
        """Pickle."""
        pickle_dict = self.__dict__.copy()
        # can't be pickled
        pickle_dict['functions'] = None
        return pickle_dict

    def __setstate__(self, pickle_dict):
        """Unpickle."""
        self.__dict__.update(pickle_dict)
        self._init_functions()


    ######################################################################
    # string functions

    def value_instr(self, ins):
        """INSTR: find substring in string."""
        util.require_read(ins, ('(',))
        big, small, n = '', '', 1
        # followed by coma so empty will raise STX
        s = self.parser.parse_expression(ins, self.session)
        if s[0] != '$':
            n = values.pass_int_unpack(s)
            error.range_check(1, 255, n)
            util.require_read(ins, (',',))
            s = self.parser.parse_expression(ins, self.session, empty_err=error.STX)
        big = values.pass_string(s)
        util.require_read(ins, (',',))
        s = self.parser.parse_expression(ins, self.session, empty_err=error.STX)
        small = values.pass_string(s)
        util.require_read(ins, (')',))
        #
        big, small = self.session.strings.copy(big), self.session.strings.copy(small)
        if big == '' or n > len(big):
            return values.null('%')
        # BASIC counts string positions from 1
        find = big[n-1:].find(small)
        if find == -1:
            return values.null('%')
        return values.int_to_integer_signed(n + find)

    def value_mid(self, ins):
        """MID$: get substring."""
        util.require_read(ins, ('(',))
        s = self.session.strings.copy(values.pass_string(self.parser.parse_expression(ins, self.session)))
        util.require_read(ins, (',',))
        start = values.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        if util.skip_white_read_if(ins, (',',)):
            num = values.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        else:
            num = len(s)
        util.require_read(ins, (')',))
        #
        error.range_check(1, 255, start)
        error.range_check(0, 255, num)
        if num == 0 or start > len(s):
            return values.null('$')
        start -= 1
        stop = start + num
        stop = min(stop, len(s))
        return self.session.strings.store(s[start:stop])

    def value_left(self, ins):
        """LEFT$: get substring at the start of string."""
        util.require_read(ins, ('(',))
        s = self.session.strings.copy(values.pass_string(self.parser.parse_expression(ins, self.session)))
        util.require_read(ins, (',',))
        stop = values.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.require_read(ins, (')',))
        #
        error.range_check(0, 255, stop)
        if stop == 0:
            return values.null('$')
        stop = min(stop, len(s))
        return self.session.strings.store(s[:stop])

    def value_right(self, ins):
        """RIGHT$: get substring at the end of string."""
        util.require_read(ins, ('(',))
        s = self.session.strings.copy(values.pass_string(self.parser.parse_expression(ins, self.session)))
        util.require_read(ins, (',',))
        stop = values.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.require_read(ins, (')',))
        #
        error.range_check(0, 255, stop)
        if stop == 0:
            return values.null('$')
        stop = min(stop, len(s))
        return self.session.strings.store(s[-stop:])

    def value_string(self, ins):
        """STRING$: repeat characters."""
        util.require_read(ins, ('(',))
        n = values.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        error.range_check(0, 255, n)
        util.require_read(ins, (',',))
        j = self.parser.parse_expression(ins, self.session)
        if j[0] == '$':
            j = self.session.strings.copy(j)
            error.range_check(1, 255, len(j))
            j = ord(j[0])
        else:
            j = values.pass_int_unpack(j)
            error.range_check(0, 255, j)
        util.require_read(ins, (')',))
        #
        return self.session.strings.store(chr(j)*n)

    ######################################################################
    # console functions

    def value_screen(self, ins):
        """SCREEN: get char or attribute at a location."""
        util.require_read(ins, ('(',))
        row = values.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.require_read(ins, (',',), err=error.IFC)
        col = values.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        z = 0
        if util.skip_white_read_if(ins, (',',)):
            z = values.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        cmode = self.session.screen.mode
        error.range_check(1, cmode.height, row)
        if self.session.screen.view_set:
            error.range_check(self.session.screen.view_start, self.session.screen.scroll_height, row)
        error.range_check(1, cmode.width, col)
        error.range_check(0, 255, z)
        util.require_read(ins, (')',))
        if z and not cmode.is_text_mode:
            return values.null('%')
        else:
            return values.int_to_integer_signed(self.session.screen.apage.get_char_attr(row, col, z!=0))

    def value_input(self, ins):
        """INPUT$: get characters from the keyboard or a file."""
        util.require_read(ins, ('$',))
        util.require_read(ins, ('(',))
        num = values.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        error.range_check(1, 255, num)
        infile = self.session.devices.kybd_file
        if util.skip_white_read_if(ins, (',',)):
            infile = self.session.files.get(self.parser.parse_file_number_opthash(ins, self.session))
        util.require_read(ins, (')',))
        word = bytearray(infile.read_raw(num))
        if len(word) < num:
            # input past end
            raise error.RunError(error.INPUT_PAST_END)
        return self.session.strings.store(word)

    def value_inkey(self, ins):
        """INKEY$: get a character from the keyboard."""
        return self.session.strings.store(self.session.keyboard.get_char())

    def value_csrlin(self, ins):
        """CSRLIN: get the current screen row."""
        row, col = self.session.screen.current_row, self.session.screen.current_col
        if (col == self.session.screen.mode.width and
                self.session.screen.overflow and
                row < self.session.screen.scroll_height):
            # in overflow position, return row+1 except on the last row
            row += 1
        return values.int_to_integer_signed(row)

    def value_pos(self, ins):
        """POS: get the current screen column."""
        # parse the dummy argument, doesnt matter what it is as long as it's a legal expression
        self.parser.parse_bracket(ins, self.session)
        col = self.session.screen.current_col
        if col == self.session.screen.mode.width and self.session.screen.overflow:
            # in overflow position, return column 1.
            col = 1
        return values.int_to_integer_signed(col)

    def value_lpos(self, ins):
        """LPOS: get the current printer column."""
        num = values.pass_int_unpack(self.parser.parse_bracket(ins, self.session))
        error.range_check(0, 3, num)
        printer = self.session.devices.devices['LPT' + max(1, num) + ':']
        if printer.device_file:
            return values.int_to_integer_signed(printer.device_file.col)
        else:
            return values.int_to_integer_signed(1)

    ######################################################################
    # file access

    def value_loc(self, ins):
        """LOC: get file pointer."""
        util.skip_white(ins)
        num = values.pass_int_unpack(self.parser.parse_bracket(ins, self.session), maxint=0xffff)
        error.range_check(0, 255, num)
        the_file = self.session.files.get(num)
        return fp.pack(fp.Single.from_int(the_file.loc()))

    def value_eof(self, ins):
        """EOF: get end-of-file."""
        util.skip_white(ins)
        num = values.pass_int_unpack(self.parser.parse_bracket(ins, self.session), maxint=0xffff)
        if num == 0:
            return values.null('%')
        error.range_check(0, 255, num)
        the_file = self.session.files.get(num, 'IR')
        return values.bool_to_integer(the_file.eof())

    def value_lof(self, ins):
        """LOF: get length of file."""
        util.skip_white(ins)
        num = values.pass_int_unpack(self.parser.parse_bracket(ins, self.session), maxint=0xffff)
        error.range_check(0, 255, num)
        the_file = self.session.files.get(num)
        return fp.pack(fp.Single.from_int(the_file.lof()))


    ######################################################################
    # env, time and date functions

    def value_environ(self, ins):
        """ENVIRON$: get environment string."""
        util.require_read(ins, ('$',))
        expr = self.parser.parse_bracket(ins, self.session)
        if expr[0] == '$':
            return self.session.strings.store(shell.get_env(self.session.strings.copy(expr)))
        else:
            expr = values.pass_int_unpack(expr)
            error.range_check(1, 255, expr)
            return self.session.strings.store(shell.get_env_entry(expr))

    def value_timer(self, ins):
        """TIMER: get clock ticks since midnight."""
        # precision of GWBASIC TIMER is about 1/20 of a second
        return fp.pack(fp.Single.from_value(
                    float(self.session.clock.get_time_ms()//50) / 20.))

    def value_time(self, ins):
        """TIME$: get current system time."""
        return self.session.strings.store(self.session.clock.get_time())

    def value_date(self, ins):
        """DATE$: get current system date."""
        return self.session.strings.store(self.session.clock.get_date())

    #######################################################
    # user-defined functions

    def value_fn(self, ins):
        """FN: get value of user-defined function."""
        fnname = self.parser.parse_scalar(ins)
        # recursion is not allowed as there's no way to terminate it
        if fnname in self.user_function_parsing:
            raise error.RunError(error.OUT_OF_MEMORY)
        try:
            varnames, fncode = self.session.user_functions[fnname]
        except KeyError:
            raise error.RunError(error.UNDEFINED_USER_FUNCTION)
        # save existing vars
        varsave = {}
        for name in varnames:
            if name in self.session.scalars.variables:
                # copy the *value* - set_var is in-place it's safe for FOR loops
                varsave[name] = self.session.scalars.variables[name][:]
        # read variables
        if util.skip_white_read_if(ins, ('(',)):
            exprs = []
            while True:
                exprs.append(self.parser.parse_expression(ins, self.session))
                if not util.skip_white_read_if(ins, (',',)):
                    break
            if len(exprs) != len(varnames):
                raise error.RunError(error.STX)
            for name, value in zip(varnames, exprs):
                self.session.scalars.set(name, value)
            util.require_read(ins, (')',))
        # execute the code
        fns = StringIO(fncode)
        fns.seek(0)
        self.user_function_parsing.add(fnname)
        value = self.parser.parse_expression(fns, self.session)
        self.user_function_parsing.remove(fnname)
        # restore existing vars
        for name in varsave:
            # re-assign the stored value
            self.session.scalars.variables[name][:] = varsave[name]
        return self.values.pass_type(fnname[-1], value)

    ###############################################################
    # graphics

    def value_point(self, ins):
        """POINT: get pixel attribute at screen location."""
        util.require_read(ins, ('(',))
        arg0 = self.parser.parse_expression(ins, self.session)
        screen = self.session.screen
        if util.skip_white_read_if(ins, (',',)):
            # two-argument mode
            arg1 = self.parser.parse_expression(ins, self.session)
            util.require_read(ins, (')',))
            if screen.mode.is_text_mode:
                raise error.RunError(error.IFC)
            return values.int_to_integer_signed(screen.drawing.point(
                            (fp.unpack(self.values.pass_single(arg0)).to_value(),
                             fp.unpack(self.values.pass_single(arg1)).to_value(), False)
                             ))
        else:
            # single-argument mode
            util.require_read(ins, (')',))
            try:
                x, y = screen.drawing.last_point
                fn = values.pass_int_unpack(arg0)
                if fn == 0:
                    return values.int_to_integer_signed(x)
                elif fn == 1:
                    return values.int_to_integer_signed(y)
                elif fn == 2:
                    fx, _ = screen.drawing.get_window_logical(x, y)
                    return fp.Single.from_value(fx)
                elif fn == 3:
                    _, fy = screen.drawing.get_window_logical(x, y)
                    return fp.Single.from_value(fy)
            except AttributeError:
                return values.null('%')

    def value_pmap(self, ins):
        """PMAP: convert between logical and physical coordinates."""
        util.require_read(ins, ('(',))
        coord = self.parser.parse_expression(ins, self.session)
        util.require_read(ins, (',',))
        mode = values.pass_int_unpack(self.parser.parse_expression(ins, self.session))
        util.require_read(ins, (')',))
        error.range_check(0, 3, mode)
        screen = self.session.screen
        if screen.mode.is_text_mode:
            return values.null('%')
        if mode == 0:
            value, _ = screen.drawing.get_window_physical(fp.unpack(self.values.pass_single(coord)).to_value(), 0.)
            return values.int_to_integer_signed(value)
        elif mode == 1:
            _, value = screen.drawing.get_window_physical(0., fp.unpack(self.values.pass_single(coord)).to_value())
            return values.int_to_integer_signed(value)
        elif mode == 2:
            value, _ = screen.drawing.get_window_logical(values.pass_int_unpack(coord), 0)
            return fp.Single.from_value(value)
        elif mode == 3:
            _, value = screen.drawing.get_window_logical(0, values.pass_int_unpack(coord))
            return fp.Single.from_value(value)

    #####################################################################
    # sound functions

    def value_play(self, ins):
        """PLAY: get length of music queue."""
        voice = values.pass_int_unpack(self.parser.parse_bracket(ins, self.session))
        error.range_check(0, 255, voice)
        if not(self.parser.syntax in ('pcjr', 'tandy') and voice in (1, 2)):
            voice = 0
        return values.int_to_integer_signed(self.session.sound.queue_length(voice))

    #####################################################################
    # error functions

    def value_erl(self, ins):
        """ERL: get line number of last error."""
        if self.parser.error_pos == 0:
            erl = 0
        elif self.parser.error_pos == -1:
            erl = 65535
        else:
            erl = self.session.program.get_line_number(self.parser.error_pos)
        return fp.pack(fp.Single.from_int(erl))

    def value_err(self, ins):
        """ERR: get error code of last error."""
        return values.int_to_integer_signed(self.parser.error_num)

    #####################################################################
    # pen, stick and strig

    def value_pen(self, ins):
        """PEN: poll the light pen."""
        fn = values.pass_int_unpack(self.parser.parse_bracket(ins, self.session))
        error.range_check(0, 9, fn)
        pen = self.session.pen.poll(fn)
        if pen is None or not self.session.events.pen.enabled:
            # should return 0 or char pos 1 if PEN not ON
            pen = 1 if fn >= 6 else 0
        return values.int_to_integer_signed(pen)

    def value_stick(self, ins):
        """STICK: poll the joystick."""
        fn = values.pass_int_unpack(self.parser.parse_bracket(ins, self.session))
        error.range_check(0, 3, fn)
        return values.int_to_integer_signed(self.session.stick.poll(fn))

    def value_strig(self, ins):
        """STRIG: poll the joystick fire button."""
        fn = values.pass_int_unpack(self.parser.parse_bracket(ins, self.session))
        # 0,1 -> [0][0] 2,3 -> [0][1]  4,5-> [1][0]  6,7 -> [1][1]
        error.range_check(0, 7, fn)
        return values.bool_to_integer(self.session.stick.poll_trigger(fn))

    #########################################################
    # memory and machine

    def value_fre(self, ins):
        """FRE: get free memory and optionally collect garbage."""
        val = self.parser.parse_bracket(ins, self.session)
        if val[0] == '$':
            # grabge collection if a string-valued argument is specified.
            self.session.memory.collect_garbage()
        return fp.pack(fp.Single.from_int(self.session.memory.get_free()))

    def value_peek(self, ins):
        """PEEK: read memory location."""
        addr = values.pass_int_unpack(self.parser.parse_bracket(ins, self.session), maxint=0xffff)
        if self.session.program.protected and not self.parser.run_mode:
            raise error.RunError(error.IFC)
        return values.int_to_integer_signed(self.session.all_memory.peek(addr))

    def value_varptr(self, ins):
        """VARPTR, VARPTR$: get memory address for variable or FCB."""
        dollar = util.skip_white_read_if(ins, ('$',))
        util.require_read(ins, ('(',))
        if (not dollar) and util.skip_white(ins) == '#':
            filenum = self.parser.parse_file_number_opthash(ins, self.session)
            var_ptr = self.session.memory.varptr_file(filenum)
        else:
            name, indices = self.parser.parse_variable(ins, self.session)
            var_ptr = self.session.memory.varptr(name, indices)
        util.require_read(ins, (')',))
        if var_ptr < 0:
            raise error.RunError(error.IFC)
        var_ptr = values.int_to_integer_unsigned(var_ptr)
        if dollar:
            return self.session.strings.store(chr(values.byte_size[name[-1]]) + values.integer_to_bytes(var_ptr))
        else:
            return var_ptr

    def value_usr(self, ins):
        """USR: get value of machine-code function; not implemented."""
        util.require_read(ins, tk.digit)
        self.parser.parse_bracket(ins, self.session)
        logging.warning("USR function not implemented.")
        return values.null('%')

    def value_inp(self, ins):
        """INP: get value from machine port."""
        port = values.pass_int_unpack(self.parser.parse_bracket(ins, self.session), maxint=0xffff)
        return values.int_to_integer_signed(self.session.machine.inp(port))

    def value_erdev(self, ins):
        """ERDEV$: device error string; not implemented."""
        if util.skip_white_read_if(ins, ('$',)):
            logging.warning("ERDEV$ function not implemented.")
            return values.null('$')
        else:
            logging.warning("ERDEV function not implemented.")
            return values.null('%')

    def value_exterr(self, ins):
        """EXTERR: device error information; not implemented."""
        x = values.pass_int_unpack(self.parser.parse_bracket(ins, self.session))
        error.range_check(0, 3, x)
        logging.warning("EXTERR function not implemented.")
        return values.null('%')

    def value_ioctl(self, ins):
        """IOCTL$: read device control string response; not implemented."""
        util.require_read(ins, ('$',))
        util.require_read(ins, ('(',))
        num = self.parser.parse_file_number_opthash(ins, self.session)
        util.require_read(ins, (')',))
        self.session.files.get(num)
        logging.warning("IOCTL$ function not implemented.")
        raise error.RunError(error.IFC)

    ###########################################################
    # unary functions

    def value_func(self, ins, fn):
        """Return value of unary function."""
        return fn(self.parser.parse_bracket(ins, self.session))

    def value_rnd(self, ins):
        """RND: get pseudorandom value."""
        if util.skip_white(ins) == '(':
            return self.session.randomiser.rnd(self.values.pass_single(self.parser.parse_bracket(ins, self.session)))
        else:
            return self.session.randomiser.rnd()
