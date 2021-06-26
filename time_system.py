from decimal import Decimal
import re


regex_chars = ['\\', '|', '[', ']', '{', '}', '.', '^', '$', '*', '+', '(', ')']

def regex_escape_str(regex_str):
    """
    Takes a string and escapes it so that it cannot mess with a regex pattern
        when put in one.
    """
    for char in regex_chars:
        regex_str = regex_str.replace(f'{char}', f'\\{char}')

    return regex_str


def split_inclusive(pattern:str, string:str, flags:int=0) -> list:
    """
    Takes a string and splits it inclusively based on the given pattern.

    For example, it will turn ":Day:Month:Year:" into
        [":", "Day", ":", "Month", ":", "Year", ":"] if the regex is
        "(Day|Month|Year)".
    """
    ret_list = []
    curr_index = 0
    ran = False

    for match in re.finditer(pattern, string, flags):
        ran = True

        # Add things before the match
        if (curr_index < match.start()):
            ret_list.append(string[curr_index:match.start()])

        # Add match
        ret_list.append(string[match.start():match.end()])

        curr_index = match.end()

    # Add anything after the last match
    if curr_index < (str_len := len(string)):
        ret_list.append(string[curr_index:str_len])

    if not ran:
        return [string]
    else:
        return ret_list


allowed_date_types = (Decimal, str, int, float, tuple)
def confirm_is_type_decimal(date):
    if isinstance(date, Decimal):
        return date
    elif isinstance(date, allowed_date_types):
        return Decimal(date)
    else:
        raise AssertionError(f'The given object "{date}" was not of one of the allowed date types {allowed_date_types}.')


class TimeSystem:
    def __init__(self, name):
        super().__init__()
        self.name = name

        self._units = []
        self._exceptions = []
        self._compiled = False

    # -------------------------------------------------------------------------
    # General Methods

    def base_to_format(self, date_in_base_unit:Decimal, date_format:str):
        """
        Returns the given date_in_base_unit in the given format. The format
            should feature the name of each unit you want the date presented
            in. For example, "Day:Month:Year" would give you the day, month,
            and year seperated by colons, assuming you have units called
            "Day", "Month", and "Year" defined in your TimeSystem.
        """
        self._check_compiled()

        date_in_base_unit = confirm_is_type_decimal(date_in_base_unit)

        split_date_format = self._split_date_format(date_format)

        used_units = []

        for string in split_date_format:
            if string in self._units_by_name and not (string in used_units):
                used_units.append(string)

        for i in range(len(used_units)):
            used_units[i] = self.unit_for_unit_name(used_units[i])

        # sort so it goes [largest_unit, ..., smallest_unit]
        used_units = sorted(used_units, reverse=True, key=self._sort_so_smallest_units_first)

        unit_values = {} # {unit_name:unit_value}
        remainder = 0
        curr_num = date_in_base_unit

        # Go from larger to smaller units and figure out what the value of each one is
        for unit in used_units:
            # Get what information will be lost when converted to larger unit
            remainder = curr_num % unit.to_base(1)

            curr_num -= remainder # Make sure remainder is not taken into account later

            unit_values[unit.name] = int(unit.from_base(curr_num))

            curr_num = remainder

        # Parse through split_date_format and replace unit names with their values
        #   in ret_str
        ret_str = ''

        for string in split_date_format:
            if string in unit_values:
                ret_str += str(unit_values[string])
            else:
                ret_str += string

        return ret_str

    def format_to_base(self, date_format_with_numbers:str, date_format:str, origional_date_in_base_unit:Decimal=0):
        """
        Takes the given date_format_with_numbers and converts it to the base unit
            of this TimeSystem assuming that the date_format_with_numbers is
            formated the same as the given date_format.

        If origional_date_in_base_unit is given, then this method will make
            sure that the given date_format_with_numbers does not overwrite
            smaller units not included in it. For example, if the
            date_format_with_numbers is ":2021:" and the date_format is ":Year:",
            it will make sure that the days, hours, minutes, seconds, etc. are
            not overwritten to 0.
        """
        self._check_compiled()
        origional_date_in_base_unit = confirm_is_type_decimal(origional_date_in_base_unit)

        assert_str = f'"{date_format_with_numbers}" is not in the same format as "{date_format}".'

        split_date_format = self._split_date_format(date_format)
        split_num_date_format = split_inclusive('-{0,1}[0-9]+\.{0,1}[0-9]*', date_format_with_numbers)

        assert len(split_num_date_format) == len(split_num_date_format), assert_str

        unit_values = {} # {unit_name:unit_value}
        units_used = []

        date_in_base_unit = 0

        for i in range(len(split_num_date_format)):
            date_form_str = split_date_format[i]
            num_date_str = split_num_date_format[i]

            if (not (date_form_str in self._units_by_name)):
                # Make sure that all delimeters are the same
                assert num_date_str == date_form_str, assert_str

                continue

            # It must be a number
            unit = self.unit_for_unit_name(date_form_str) # Get unit of number
            units_used.append(unit)
            date_in_base_unit += unit.to_base(Decimal(num_date_str))

        # sort so it goes [largest_unit, ..., smallest_unit]
        units_used.sort(reverse=True, key=self._sort_so_smallest_units_first)

        orig_remainder = date_in_base_unit # Will be the number of base units not affected by date_format_with_numbers
        for unit in units_used:
            # Get what information will be lost when converted to larger unit
            orig_remainder = orig_remainder % unit.to_base(1)

        # This will make it so that smaller units will not be affected
        #   (setting the day will not affect the extra minutes or seconds)
        date_in_base_unit += orig_remainder

        return date_in_base_unit

    def unit_for_unit_name(self, unit_name:str):
        self._check_compiled()
        assert unit_name in self._units_by_name, f'There is no defined unit in the {self.name} TimeSystem with the name \"{unit_name}\"'
        return self._units_by_name[unit_name]

    def unit_to_base_unit(self, date_in_unit:Decimal, unit_name:str):
        self._check_compiled()

        date_in_unit = confirm_is_type_decimal(date_in_unit)

        unit = self.unit_for_unit_name(unit_name)
        return unit.to_base(date_in_unit)

    def base_unit_to_unit(self, date_in_base_unit:Decimal, unit_name:str):
        self._check_compiled()

        date_in_base_unit = confirm_is_type_decimal(date_in_base_unit)

        unit = self.unit_for_unit_name(unit_name)
        return unit.from_base(date_in_base_unit)

    def add_unit(self, name, conversion_factor:Decimal=Decimal(1), parent_unit_name:str=None):
        assert not (name in [u.name for u in self._units]), 'You cannot have two units with the same name in the TimeSystem.'
        assert conversion_factor > 0, "The conversion factor between units must always be greater than 0."
        conversion_factor = confirm_is_type_decimal(conversion_factor)
        self._units.append(self.Unit(name, conversion_factor, parent_unit_name))
        self._compiled = False

    def add_exception(self, interval_amount:Decimal, interval_amount_unit_name:str, add_amount:Decimal, add_amount_unit_name:str):
        interval_amount = confirm_is_type_decimal(interval_amount)
        add_amount = confirm_is_type_decimal(add_amount)
        interval_amount = Decimal(interval_amount) if not isinstance(interval_amount, Decimal) else interval_amount
        add_amount = Decimal(add_amount) if not isinstance(add_amount, Decimal) else add_amount

        self._exceptions.append(self.TimeException(interval_amount, interval_amount_unit_name, add_amount, add_amount_unit_name))
        self._compiled = False

    def compile(self):
        """
        This method sets up the time system so that unit conversions can be done
            correctly. It should be run after all units and exceptions
            have been defined for the system.
        """
        # Clean everything in case this TimeSystem was compiled before
        self._units_by_name = {}
        self._exceptions_by_interval_unit = {}
        self._base_unit = None

        for unit in self._units:
            unit.set_parent_unit(None)
            unit.children = []

        # Put all units in dictionary by name
        for unit in self._units:
            assert not (unit.name in self._units_by_name), f'There cannot be two units with the same name. Name in conflict: {unit.name}.'
            self._units_by_name[unit.name] = unit

        # Set up unit hierarchy
        for unit in self._units:
            if unit.parent_unit_name is not None:
                assert unit.parent_unit_name in self._units_by_name, 'The unit named {unit.parent_unit_name} is undefined.'
                parent_unit = self._units_by_name[unit.parent_unit_name]
                unit.set_parent_unit(parent_unit)
                parent_unit.children.append(unit)
            else:
                assert self._base_unit is None, 'You cannot have two base units.'
                unit.set_parent_unit(None)
                self._base_unit = unit

        self._compiled = True

        # --------------
        # Now figure out working conversion factors (the ones used when actually estimating conversions)

        # First, set the units to all have their initial conversion factor as their working conversion factor
        for unit in self._units:
            unit.set_working_conversion_factor(unit.get_initial_conversion_factor())

        for exception in self._exceptions:
            interval_unit = self.unit_for_unit_name(exception.interval_amount_unit_name)
            add_amt_unit = self.unit_for_unit_name(exception.add_amount_unit_name)

            lin = interval_unit.get_lineage()
            lin.reverse()
            lin.pop(0) # Remove the unit itself from the lineage so that it only contains units smaller than itself
            assert add_amt_unit in lin, f'A {add_amt_unit.name} is not in the lineage of a(n) {interval_unit.name}. For exceptions, the unit of the amount being added must be in the same lineage as the unit of the interval of the addition. For example, the exception "Every 4 years, add a day" would work because a day is directly between a year and a the base unit of the system, a second. "Every 4 Years, add a Millenia" would not work because it is not only is a millenia larger than a year, but you do not need to convert years to millenia in order to get to the base unit, seconds.'

        # Now, go from smaller units to larger units and figure out their conversion_factor
        stack = [] if self._base_unit is None else [self._base_unit]

        while len(stack) > 0:
            curr_unit = stack.pop()
            stack.extend(curr_unit.children)

            base_amt = curr_unit.to_base(Decimal(1))

            difs = []
            rel_exceptions = []

            # Find all exceptions relevant to this unit
            for exception in self._exceptions:
                if exception.interval_amount_unit_name == curr_unit.name:
                    rel_exceptions.append(exception)

            # Now go through the relevant exceptions and see what one of the unit
            #   would be in base unit with the added time from each relevant exception
            for exception in rel_exceptions:
                curr_num = Decimal(1)

                # Lineage is [curr_unit, ..., base_unit]
                for unit in reversed(curr_unit.get_lineage()):
                    if unit.name == exception.add_amount_unit_name:
                        curr_num += exception.add_amount

                    # Convert to lower unit (Day to Hour, Hour to Minute, Minute to Second)
                    curr_num *= unit.get_working_conversion_factor()

                # curr_num is now the amount that one of the curr_unit is in the
                #   base unit

                difs.append((curr_num - base_amt) / exception.interval_amount)

            add_amt = Decimal(0)
            for dif in difs:
                add_amt += dif

            parent_unit = curr_unit.get_parent_unit()
            working_con_factor = 1 if parent_unit is None else parent_unit.from_base(base_amt + add_amt)

            curr_unit.set_working_conversion_factor(working_con_factor)

        self._compiled = True

    # -------------------------------------------------------------------------
    # Helper Methods

    def _sort_so_smallest_units_first(self, unit):
        """
        Use this method as the key to a sort method and it will sort the list
            of units from small to large.
        """
        return unit.get_working_conversion_factor()

    def _get_unit_names_regex(self):
        """
        Returns a regular expression that can be used to find all instances of
            unit names in a string.
        """
        unit_names_regex = '('
        for i, unit_name in enumerate(self._units_by_name.keys()):
            if i > 0:
                unit_names_regex += r'|'
            unit_names_regex += regex_escape_str(unit_name)
        unit_names_regex += ')'

        return unit_names_regex

    def _split_date_format(self, date_format:str):
        """
        Takes a format in a string and splits it inclusively.

        For example, it will turn ":Day:Month:Year:" into
            [":", "Day", ":", "Month", ":", "Year", ":"] (assuming you have defined
            units with the names "Day", "Month", and "Year") and return it.
        """
        self._check_compiled()
        unit_names_regex = self._get_unit_names_regex()
        return split_inclusive(unit_names_regex, date_format)

    def _check_compiled(self):
        assert self._compiled, 'You must compile the TimeSystem before using it.'

    def _unit_for_unit_name(self, unit_name:str):
        assert unit_name in self._units_by_name, f'There is no defined unit in the {self.name} TimeSystem with the name \"{unit_name}\"'
        return self._units_by_name[unit_name]

    # -------------------------------------------------------------------------
    # Helper Classes

    class TimeException:
        def __init__(self, interval_amount:Decimal, interval_amount_unit_name:str, add_amount:Decimal, add_amount_unit_name:str):
            super().__init__()

            assert interval_amount > 0, 'The interval that causes time to be added must be greater than 0.'

            interval_amount = confirm_is_type_decimal(interval_amount)
            add_amount = confirm_is_type_decimal(add_amount)

            self.interval_amount = interval_amount # amount of time till this exception comes into affect
            self.interval_amount_unit_name = interval_amount_unit_name # the name of the unit that the inteval amount is in
            self.add_amount = add_amount # how much time to add every time interval happens (can be negative)
            self.add_amount_unit_name = add_amount_unit_name

        def __repr__(self):
            return f'TimeException(Every {self.interval_amount} {self.interval_amount_unit_name}(s), add {self.add_amount} {self.add_amount_unit_name}(s))'

    class Unit:
        def __init__(self, name:str, conversion_factor:Decimal=Decimal(1), parent_unit_name:str=None):
            super().__init__()
            conversion_factor = confirm_is_type_decimal(conversion_factor)

            self.name = name
            self.parent_unit_name = parent_unit_name
            self.conversion_factor = conversion_factor
            self.children = []

        # ---------------------------------------------------------------------
        # Getters and Setters

        def set_parent_unit(self, parent_unit):
            self._parent_unit = parent_unit

        def get_parent_unit(self):
            self._check_has('_parent_unit')
            return self._parent_unit

        def set_working_conversion_factor(self, conversion_factor):
            """
            Sets the working conversion factor that is found when the TimeSystem
                is compiled.
            """
            self._working_conversion_factor = conversion_factor

        def get_working_conversion_factor(self):
            self._check_has('_working_conversion_factor')
            return self._working_conversion_factor

        # ---------------------------------------------------------------------
        # Other Methods

        def _check_has(self, attr):
            assert hasattr(self, attr), f'The parent unit of {self.name} has not been set yet. Probably need to compile the TimeSystem.'

        def to_base(self, date_in_this_unit:Decimal):
            """
            Converts the number in this unit to the base unit of this TimeSystem.
            """
            date_in_this_unit = confirm_is_type_decimal(date_in_this_unit)
            parent = self.get_parent_unit()
            return date_in_this_unit if parent is None else parent.to_base(date_in_this_unit) * self.get_working_conversion_factor()

        def from_base(self, date_in_base_unit:Decimal):
            """
            Converts the number in base unit to this unit of this TimeSystem.
            """
            date_in_base_unit = confirm_is_type_decimal(date_in_base_unit)
            parent = self.get_parent_unit()
            return date_in_base_unit if parent is None else parent.from_base(date_in_base_unit) / self.get_working_conversion_factor()

        def get_initial_conversion_factor(self):
            """
            Returns the conversion factor to get to the parent unit of this unit.
            """
            return self.conversion_factor

        def get_lineage(self):
            """
            Returns a list of the lineage of this unit going from the base unit
                to this one.
            """
            if self.get_parent_unit() is None:
                return [self]

            line = self.get_parent_unit().get_lineage()
            line.append(self)
            return line

        def __repr__(self):
            return f"Unit(name={self.name}, initial_conversion_factor={self.get_initial_conversion_factor()}, parent={self.get_parent_unit()})"

if __name__ == '__main__':
    greg_calander = TimeSystem('Gregorian')

    greg_calander.add_unit('Second') # The base unit is the Second
    greg_calander.add_unit('Minute', 60, 'Second') # A minute is 60 Seconds
    greg_calander.add_unit('Hour', 60, 'Minute')
    greg_calander.add_unit('Day', 24, 'Hour')
    greg_calander.add_unit('Year', 365, 'Day')

    greg_calander.compile()

    print("")
    print("__Basic_Unit_Conversion__")

    def test_unit_to_base(date_in_unit, unit_name):
        date_in_base = greg_calander.unit_to_base_unit(date_in_unit, unit_name)
        print(f'There are {date_in_base} {greg_calander._base_unit.name}(s) in {date_in_unit} {unit_name}(s)')
        return date_in_base

    def test_base_to_unit(date_in_base, unit_name):
        date_in_unit = greg_calander.base_unit_to_unit(date_in_base, unit_name)
        print(f'There are {date_in_base} {greg_calander._base_unit.name}(s) in {date_in_unit} {unit_name}(s)')
        return date_in_unit

    year_in_sec = test_unit_to_base(1, 'Year')
    assert year_in_sec == 31536000, 'Conversion from Years to Seconds is Wrong.'
    assert test_base_to_unit(year_in_sec, 'Year') == 1, 'For some reason, the conversion back to Years is wrong'


    print("")
    print("__Unit_Conversion_With_Exceptions__")

    # Add the exceptions that make the Gregorian Calander work
    greg_calander.add_exception(4, 'Year', 1, 'Day') # Every 4 Years, add 1 Day
    greg_calander.add_exception(100, 'Year', -1, 'Day') # Every 100 Years, add -1 Day to get rid of leap year
    greg_calander.add_exception(400, 'Year', 1, 'Day') # Every 400 Years, add 1 Day to add leap year back

    greg_calander.compile()

    year_in_sec = test_unit_to_base(1, 'Year')
    assert year_in_sec == 31556952, 'Conversion from Years to Seconds is Wrong.'
    assert test_base_to_unit(year_in_sec, 'Year') == 1, 'For some reason, the conversion back to Years is wrong'

    day_in_sec = test_unit_to_base(1, 'Day')

    test_base_to_unit(test_unit_to_base(1, 'Year'), 'Year')

    print("")
    print("__Base_To_Format__")

    def base_to_format_test(date_in_base, date_format, desired_date_format_result):
        in_base_format = greg_calander.base_to_format(date_in_base, date_format)
        print(f'{date_in_base} Second(s) = {in_base_format} ({date_format})')
        assert in_base_format == desired_date_format_result, f'Format is wrong. Should be: {desired_date_format_result}'

    base_to_format_test(year_in_sec, ':Year:Day:Second:', ':1:0:0:')
    base_to_format_test(year_in_sec + 1, ':Year:Day:Second:', ':1:0:1:')
    base_to_format_test(year_in_sec + day_in_sec, ':Year:Day:Second:', ':1:1:0:')
    base_to_format_test(year_in_sec + (day_in_sec * 100) + 1, ':Year:Day:Second:', ':1:100:1:')
    base_to_format_test((year_in_sec * 2021) + (day_in_sec * 21) + 1, ':Year:Day:Second:', ':2021:21:1:')

    print("")
    print("__Format_To_Base__")

    def format_to_base_test(date_in_format, date_format, desired_date_result, origional_date_in_base_unit=0):
        in_base_unit = greg_calander.format_to_base(date_in_format, date_format, origional_date_in_base_unit)
        print(f'({date_format}) {date_in_format} = {int(in_base_unit)} {greg_calander._base_unit.name}(s)')
        assert in_base_unit == desired_date_result, f'Date in base unit is wrong. Should be: {desired_date_result}. ({date_in_format} in {date_format}) {f"origional_date_in_base_unit: {origional_date_in_base_unit}" if origional_date_in_base_unit == 0 else ""}.'

    format_to_base_test(':2021:21:1:', ':Year:Day:Second:', (year_in_sec * 2021) + (day_in_sec * 21) + 1)

