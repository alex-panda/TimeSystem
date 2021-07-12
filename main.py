"""
This module holds the TimeSystem class that allows you to define your own
    time system with its own units. You can have your own formats for your dates
    and times and convert between different times. There is an example in
    __name__ == "__main__"

Note: This TimeSystem was modeled to be complex enough to handle the Gergorian
    Calander, but if you want something more complex then you will probably
    have to modify it.

Note: This TimeSystem is made to be consistent. If you convert 5/20/2020
    to seconds then you should get 5/20/2020 when you convert those seconds
    back into the format. It may, however, be a bit off when you are just
    trying to get the number of seconds in 100000000 Years, because it
    turns the "Every 4 years, add 1 day." into an estimate (1 Year = 365.25 Days)

TODO:
    - Allow negative formats to be given so that if a date_in_base_unit is
        given that is negative, it can be formated as such. This is useful for
        denoting dates that are in BC instead of AC
    - Make it so that the names of subdivisions can be used (so if doing Months,
        then you can say "January" instead of "1" in your format)
    - Add support for RepeatingDivisions like Weeks
"""
from decimal import Decimal, InvalidOperation
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
    """
    A class that allows you to define your own time system and allows you to
        convert from Dates/Times in formats to the Dates/Times in the base unit
        of the time system (which is useful for storage of the Date/Time if you
        want to be able to change that same Date/Time to a different format
        later).

    The nickname parameter is for being able to define nicknames such as
        Mon., Tue., Wed., etc. to values. For example, if it is a Tuesday, then
        the value will be 2 because it is the 3rd day of the week (it is zero-
        indexed, even for one_based units). It is in the following format, with
        'nick_for' being the key to get what the name of the Unit that this
        nickname is for is. For example, the format could be typed as
        'Day/wk/mn' as opposed to 'Day/Week/Month' if you want the nicknames
        below to go into affect.
        {
        'wk': {
                'nick_for': 'Week',
                'names': {
                    0: 'Sun.',
                    1: 'Mon.',
                    2: 'Tue.',
                    3: 'Wed.',
                    4: 'Thu.',
                    5: 'Fri.',
                    6: 'Sat.'
                }
            },
        'mn': {
                'nick_for': 'Month',
                'names': {
                    0: 'Jan.',
                    1: 'Feb.',
                    2: 'Mar.',
                    ...
                }
            }
        }
    """
    def __init__(self, name):
        super().__init__()
        self.name = name

        self._units = []
        self._exceptions = []
        self._exact_divs = []
        self._repeating_divs = []
        self._compiled = False

    # -------------------------------------------------------------------------
    # General Methods

    def base_to_format(self, date_in_base_unit:Decimal, date_format:str, neg_date_format:str=None, one_based_units:list=None, nicknames:dict=None) -> str:
        """
        Returns the given date_in_base_unit in the given format. The format
            should feature the name of each unit you want the date presented
            in. For example, "Day:Month:Year" would give you the day, month,
            and year seperated by colons, assuming you have units called
            "Day", "Month", and "Year" defined in your TimeSystem.

        one_based_units are the units where they should start at 1. For example,
            0/1/2021 does not exist because Months start at January being 1 so it
            would be 1/1/2021 so you would pass a list like ["Month", "Day"]
            to this method to make it so.

        nicknames is described in the comment for this class because it is used
            in multiple methods
        """
        self._check_compiled()

        one_based_units = [] if one_based_units is None else one_based_units
        nicknames = [] if nicknames is None else nicknames

        date_in_base_unit = confirm_is_type_decimal(date_in_base_unit)

        # Decide whether the neg_date_format should be used or not
        should_be_neg = False
        if date_in_base_unit < 0:
            date_in_base_unit *= -1 # Having the date be negative might mess things up, so make it possitive

            if neg_date_format is not None:
                should_be_neg = True

        if should_be_neg:
            split_date_format = self._split_date_format(neg_date_format, nicknames)
        else:
            split_date_format = self._split_date_format(date_format, nicknames)

        # Sort out the Units and Divisions from the other delimiting strings
        unit_values = {} # {unit_name:unit_value}
        used_units = []
        used_exact_divs = []
        used_repeating_divs = []

        for i in range(len(split_date_format)):
            string = split_date_format[i]

            # Change out nicknames for proper names of units/divisions
            if string in nicknames:
                string = nicknames[string]['nick_for']

            if string in self._units_by_name:
                unit = self.unit_for_unit_name(string)
                if not (unit in used_units):
                    used_units.append(unit)

            elif string in self._exact_divs_by_name:
                div = self._exact_div_for_exact_div_name(string)
                if not (div in used_exact_divs):
                    used_exact_divs.append(div)

            elif string in self._repeating_divs_by_name:
                div = self._repeating_div_for_repeating_div_name(string)
                if not (div in used_repeating_divs):
                    used_repeating_divs.append(div)

        # ----------
        # Do Units

        # sort so it goes [largest_unit, ..., smallest_unit]
        used_units = sorted(used_units, reverse=True, key=self._sort_so_smallest_units_first)

        remainder = 0
        curr_num = date_in_base_unit

        # Go from larger to smaller units and figure out what the value of each one is
        for unit in used_units:
            # Get what information will be lost when converted to larger unit
            remainder = curr_num % unit.to_base(1)

            curr_num -= remainder # Make sure remainder is not taken into account later

            if unit.name in one_based_units:
                unit_values[unit.name] = int(unit.from_base(curr_num)) + 1
            else:
                unit_values[unit.name] = int(unit.from_base(curr_num))

            curr_num = remainder

        # ----------
        # Do ExactDivisions
        for div in used_exact_divs:
            _, offsets_in_base_unit = self._get_exact_div_offsets(date_in_base_unit, div.name)

            unit_dividing = self._unit_for_unit_name(div.name_of_unit_dividing)
            unit_dividing_into = self._unit_for_unit_name(div.name_of_unit_dividing_into)
            remainder = date_in_base_unit % unit_dividing.to_base(1)
            total_offset = 0
            for i in range(len(offsets_in_base_unit)):
                # If offsets are:
                #   ["January", "February", "March"]
                #   [       31,         28,      31]
                #   and it is March, then after subtracting 31, 28, and 31
                #   from the remainder should make the remainder negative
                remainder -= offsets_in_base_unit[i]
                if remainder <= 0:
                    if not (div.name in unit_values):

                        if div.name in one_based_units:
                            unit_values[div.name] = i + 1
                        else:
                            unit_values[div.name] = i

                        unit_dividing_into_name = div.name_of_unit_dividing_into

                        if unit_dividing_into_name in unit_values:
                            unit_values[unit_dividing_into_name] -= int(unit_dividing_into.from_base(total_offset))
                    break
                total_offset += offsets_in_base_unit[i]

        # ----------
        # Do RepeatingDivisions
        for div in self._repeating_divs:
            unit_in = self._unit_for_unit_name(div.name_of_unit_in)

            rep_time_in_base_unit = unit_in.to_base(unit_in)
            remainder = date_in_base_unit % rep_time_in_base_unit

            offset_names = [o[0] for o in div.division_defs]
            offsets_in_base = [unit_in.to_base(o[1]) for o in div.division_defs]

            for i in range(len(offset_names)):
                remainder -= offsets_in_base[i]

                if remainder <= 0:
                    if not (div.name in unit_values):
                        if div.name in one_based_units:
                            unit_values[div.name] = i + 1
                        else:
                            unit_values[div.name] = i

                    break

        # ----------
        # Parse through split_date_format and replace unit names with their values
        #   in ret_str
        ret_str = ''

        for string in split_date_format:
            unit_str = string
            if string in nicknames:
                unit_str = nicknames[string]['nick_for']
                nick_vals = nicknames['names']
            else:
                nick_vals = {}

            if unit_str in unit_values:
                val = unit_values[unit_str]

                if val in nick_vals:
                    ret_str += str(nick_vals[val])

                else:
                    ret_str += str(val)
            else:
                ret_str += string

        return ret_str

    def format_to_base(self, date_format_with_numbers:str, date_format:str, origional_date_in_base_unit:Decimal=Decimal(0), neg_date_format:str=None, one_based_units:list=None, nicknames:dict=None) -> int:
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

        If you want a date to be negative (i.e. BC as opposed to AC) you must
            put give a format for the neg_date_format and the date_format_with_numbers
            must match it moreso than the positive date_format.

        one_based_units are the units where they should start at 1. For example,
            0/1/2021 does not exist because Months start at January being 1 so it
            would be 1/1/2021 so you would pass a list like ["Month", "Day"]
            to this method to make it so.

        nicknames is described in the comment for this class because it is used
            in multiple methods
        """
        self._check_compiled()

        one_based_units = [] if one_based_units is None else one_based_units
        nicknames = [] if nicknames is None else nicknames

        origional_date_in_base_unit = confirm_is_type_decimal(origional_date_in_base_unit)

        nicknames_set = set()
        for _, val in nicknames:
            nicknames_set.update(val['names'].values())

        # Split formats
        split_num_date_format = split_inclusive('[0-9]+\.{0,1}[0-9]*', date_format_with_numbers)
        split_pos_date_format = self._split_date_format(date_format, nicknames_set)
        is_neg = False

        # Handle it if there is a negative format given
        if neg_date_format:
            # since possibly in negative date format, we must figure out whether
            #   the date_format_with_numbers is actually in the negative
            #   format or not
            split_neg_date_format = self._split_date_format(neg_date_format, nicknames_set)

            pos_date = self._check_formats_same(split_num_date_format, split_pos_date_format, nicknames_set)
            neg_date = self._check_formats_same(split_num_date_format, split_neg_date_format, nicknames_set)

            assert not (neg_date and pos_date), \
                    f'You gave both the positive date format "{date_format}" and the negative date format "{neg_date_format}" but they both match the given date_format_with_numbers "{date_format_with_numbers}".'
            assert neg_date or pos_date, \
                    f'You gave both the positive date format "{date_format}" and the negative date format "{neg_date_format}" but neither of them match the given date_format_with_numbers "{date_format_with_numbers}".'

            if pos_date:
                split_date_format = split_pos_date_format
            else:
                split_date_format = split_neg_date_format
                is_neg = True

        else:
            split_date_format = split_pos_date_format

        units_in_base_unit = {} # {unit_name:unit_value}
        units_used = []
        exact_divs_used = []
        rep_divs_used = []

        assert len(split_date_format) == len(split_num_date_format), \
                f'You probably forgot to define/add a Unit or Division. {split_date_format} is not in format {split_num_date_format}'

        # Actually convert each defined unit to its value in the base unit
        for i in range(len(split_num_date_format)):
            date_form_str = split_date_format[i]
            num_date_str = split_num_date_format[i]

            # Abreviations like 'MN' need to be turned into what they stand for
            #   example: 'MN' turned into 'Month'
            if date_form_str in nicknames:
                date_form_str = nicknames[date_form_str]['nick_for']

            # If num_date_str str is a nickname (i.e. Mon., Tue., Wed., etc.) then
            #   convert it to its value (0, 1, 2, etc.)
            if num_date_str in nicknames_set:
                for type_as, val in nicknames:
                    for key, value in val['names']:
                        if num_date_str == value:
                            num_date_str = key
                            break_out = True
                            break
                    if break_out:
                        break

            # Evaluate Units to base Unit
            if date_form_str in self._units_by_name:
                unit = self.unit_for_unit_name(date_form_str) # Get unit of number
                if not (unit in units_used):
                    units_used.append(unit)

                if unit.name in one_based_units:
                    unit_in_base_unit = unit.to_base(Decimal(num_date_str) - 1)
                else:
                    unit_in_base_unit = unit.to_base(Decimal(num_date_str))

                unit_name = unit.name
                if unit_name in units_in_base_unit:
                    assert unit_in_base_unit == units_in_base_unit[unit_name], \
                            f'You specified "{unit_name}" twice in your format, but did not give it the same value both times.'

                units_in_base_unit[unit_name] = unit_in_base_unit

            # Note ExactDivisions
            elif date_form_str in self._exact_divs_by_name:
                if date_form_str in one_based_units:
                    exact_divs_used.append((date_form_str, int(num_date_str) - 1))
                else:
                    exact_divs_used.append((date_form_str, int(num_date_str)))

            # Note RepeatingDivisions
            elif date_form_str in self._repeating_divs_by_name:
                if date_form_str in one_based_units:
                    rep_divs_used.append((date_form_str, int(num_date_str - 1)))
                else:
                    rep_divs_used.append((date_form_str, int(num_date_str)))

        # --------
        # Now find date_in_base_unit without Divisions added
        date_in_base_unit = Decimal(0)
        for unit_in_base_unit in units_in_base_unit.values():
            date_in_base_unit += unit_in_base_unit

        # Now figure out exact divisions

        time_to_add = 0
        for exact_div_tuple in exact_divs_used:
            div_name = exact_div_tuple[0]
            offset_index = exact_div_tuple[1] # Index of what offset to add

            div = self._exact_div_for_exact_div_name(div_name)
            div_into_unit = self._unit_for_unit_name(div.name_of_unit_dividing_into)
            if not (div_into_unit in units_used):
                units_used.append(div_into_unit)

            _, offsets = self._get_exact_div_offsets(date_in_base_unit, div_name)

            # If offsets are:
            #   ["January", "February", "March"]
            #   [       31,         28,      31]
            # and it is march, then the offset is 31 + 28 in order to get to march
            for i in range(len(offsets)):
                if i < offset_index:
                   time_to_add += offsets[i]
                else:
                    break

        date_in_base_unit += time_to_add

        # Now figure out repeating divisions, making the current date allign
        #   with them.
        for rep_div_tuple in rep_divs_used:
            div_name = rep_div_tuple[0]
            target_day = rep_div_tuple[1] # Index of what day of the week it supposed to be

            div = self._repeating_div_for_repeating_div_name(div_name)

            div_total = Decimal(0)
            unit_in = self._unit_for_unit_name(div.name_of_unit_in)
            for div_def in div.division_defs:
                div_total += div_def[1]
            div_total = unit_in.to_base(div_total)

            remainder = date_in_base_unit % div_total

            curr_day = int(unit_in.from_base(remainder)) # What day of the week it currently is

            time_to_add = Decimal(0)

            if curr_day < target_day:
                # must add time to get to target day
                for i, div_def in enumerate(div.division_defs):
                    if i >= target_day:
                        break

                    if i >= curr_day:
                        # Add amount of time to get to next day
                        time_to_add += div_def[1]

                date_in_base_unit += unit_in.to_base(time_to_add)

            elif target_day > curr_day:
                # Must subtract time to get to target day
                for i, div_def in enumerate(reversed(div.division_defs)):
                    if i >= len(div.division_defs) - curr_day - 1:
                        break

                    if i >= len(div.division_defs) - target_day - 1:
                        # Add amount of time to get to next day
                        time_to_add += div_def[1]

                date_in_base_unit -= unit_in.to_base(time_to_add)

            if not (div.name_of_unit_in in units_used):
                units_used.append(div.name_of_unit_in)

        # --------
        # Make sure that no units larger or smaller than specified are overwritten
        #   to 0

        # sort so it goes [largest_unit, ..., smallest_unit]
        units_used.sort(reverse=True, key=self._sort_so_smallest_units_first)

        # Make it so that when you set Year/Day, it does not also set smaller
        #   units like Second to 0 just because they were not specified
        orig_remainder_small = origional_date_in_base_unit  % units_used[-1].to_base(1) # Will be the number of base units not affected by date_format_with_numbers
        date_in_base_unit += orig_remainder_small

        # Make it so that when you set Day/Hour, it does not also set larger
        #   units like Year to 0 because the larger units weren't specified
        larger_unit_name = units_used[0].parent_unit_name

        if larger_unit_name is not None:
            orig_remainder_large = origional_date_in_base_unit % self.unit_for_unit_name(larger_unit_name).to_base(1)
            orig_remainder_large = origional_date_in_base_unit - orig_remainder_large
        else:
            orig_remainder_large = 0

        # If the date is supposed to negative (i.e. BC instead of AC), make the
        #   the date_in_base_unit negative
        if is_neg:
            date_in_base_unit *= -1

        # Return date in base unit
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
        """
        Add a unit to the TimeSystem such as "Minute", "Hour", "Day"
        """
        assert not (name in [u.name for u in self._units]), 'You cannot have two units with the same name in the TimeSystem.'
        assert conversion_factor > 0, "The conversion factor between units must always be greater than 0."
        conversion_factor = confirm_is_type_decimal(conversion_factor)
        self._units.append(self.Unit(name, conversion_factor, parent_unit_name))
        self._compiled = False

    def add_exception(self, name:str, interval_amount:Decimal, interval_amount_unit_name:str, add_amount:Decimal, add_amount_unit_name:str):
        """
        Add an exception to the TimeSystem such as "Every Year is 365 Days long except every 4 Years a Year is 366 Days long."

        When adding one of these, think of the arguments as meaning
            "Every interval_amount interval_amount_unit_name add add_amount add_amount_unit_name."
            i.e. "Every 4 Years add 1 Day"
        """
        interval_amount = confirm_is_type_decimal(interval_amount)
        add_amount = confirm_is_type_decimal(add_amount)

        self._exceptions.append(self.TimeException(name, interval_amount, interval_amount_unit_name, add_amount, add_amount_unit_name))
        self._compiled = False

    def add_exact_division(self, name:str, name_of_unit_dividing:str, name_of_unit_dividing_into:str, division_defs:list, division_corrections:list):
        """
        Add an ExactDivision of a unit. For example, a Month is an ExactDivision
            of a Year because a Year is 12 Months and every month is labeled
            with the extra leap days being accounted for every 4 years.
        """
        self._exact_divs.append(self.ExactDivision(name, name_of_unit_dividing, name_of_unit_dividing_into, division_defs, division_corrections))
        self._compiled = False

    def add_repeating_division(self, name:str, name_of_unit_in:str, division_defs:list):
        """
        Add a RepeatingDivision such as a Week that just repeats over and over
            again throughout the Year without conforming to TimeExceptions i.e.
            without adding a day to account for Leap Days.
        """
        self._repeating_divs.append(self.RepeatingDivision(name, name_of_unit_in, division_defs))
        self._compiled = False

    def compile(self):
        """
        This method sets up the time system so that unit conversions can be done
            correctly. It should be run after all units and exceptions
            have been defined for the system.
        """
        # Clean everything in case this TimeSystem was compiled before
        self._units_by_name = {}
        self._exceptions_by_name = {}
        self._exact_divs_by_name = {}
        self._repeating_divs_by_name = {}
        self._base_unit = None

        for unit in self._units:
            unit.set_parent_unit(None)
            unit.children = []

        # Put all Units in dictionary by name
        for unit in self._units:
            assert not (unit.name in self._units_by_name), f'There cannot be two Units with the same name. Name in conflict: {unit.name}.'
            self._units_by_name[unit.name] = unit

        # Put all exceptions in dictionary by name
        for exception in self._exceptions:
            assert not (exception.name in self._exceptions_by_name), f'There cannot be two TimeExceptions with the same name. Name in conflict: {exception.name}.'
            self._exceptions_by_name[exception.name] = exception

        # Put all Repeating Divisions in dictionary by name
        for div in self._repeating_divs:
            assert not (div.name in self._repeating_divs_by_name), f'There cannot be two RepeatingDivisions with the same name. Name in conflict: {div.name}.'
            self._repeating_divs_by_name[div.name] = div

        # Put all ExactDivisions in dictionary by name
        for div in self._exact_divs:
            assert not (div.name in self._exact_divs_by_name), f'There cannot be two ExactDivisions with the same name. Name in conflict: {div.name}.'
            self._exact_divs_by_name[div.name] = div

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

        # Check that all ExactDivisions are valid
        for div in self._exact_divs:
            # Check that units have been defined (unit_for_unit_name will raise
            #   error now if they are not)
            div_dividing_unit = self.unit_for_unit_name(div.name_of_unit_dividing)
            into_unit = self.unit_for_unit_name(div.name_of_unit_dividing_into)

            # Check that the divs take into account the time added by units
            #   smaller than ore equal to the unit that they are dividing

            div_dividing_unit_lin = [x for x in reversed(div_dividing_unit.get_lineage())]
            div_dividing_unit_lin.pop(0) # Pops div_dividing_unit

            for exception in self._exceptions:
                add_amt_unit_name = exception.add_amount_unit_name
                exception_add_amt_unit = self.unit_for_unit_name(add_amt_unit_name)

                # If the exception is adding a unit that is smaller than or equal
                #   to the div_dividing_unit, then the div must account for it
                if exception_add_amt_unit in div_dividing_unit_lin:
                    # Check that the div has taken into account this added time
                    assert div.name_in_div_corrections(exception.name), \
                            f'The Division named "{div.name}" needs to take into account the time added by the TimeException named "{exception.name}".'

            for div_c in div.div_corrections:
                assert div.name_in_division_defs(div_c[1]), \
                        f"{div.name}'s correction for {div_c[0]} corrects {div_c[1]}, a subdivision that is not defined by/in {div.name}."

        # Check that all RepeatingDivisions are valid
        for div in self._repeating_divs:
            assert div.name_of_unit_in in self._units_by_name, f'"{div.name}" is in "{div.name_of_unit_in}", a Unit that has not been defined/added to the TimeSystem.'

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

        # Now, go from smaller units to larger units and figure out their
        #   average conversion_factors. For example, if an exception
        #   adds a day every 4 Years, then a Year is 365.25 Days
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

    @staticmethod
    def _sort_so_smallest_units_first(unit):
        """
        Use this method as the key to a sort method and it will sort the list
            of units from small to large.
        """
        return unit.get_working_conversion_factor()

    def _get_names_regex(self, hints:iter=None):
        """
        Returns a regular expression that can be used to find all instances of
            Unit names and Division names in a string.

        hints is just in iterable of other strings that you want included in the regex.
        """
        unit_names_regex = '('
        unit_names = [regex_escape_str(name) for name in self._units_by_name.keys()]
        unit_names.extend([regex_escape_str(name) for name in self._exact_divs_by_name.keys()])
        unit_names.extend([regex_escape_str(name) for name in self._repeating_divs_by_name.keys()])

        if hints is not None:
            hints = [regex_escape_str(hint) for hint in hints]
            unit_names.extend(hints)

        for i, unit_name in enumerate(unit_names):
            if i > 0:
                unit_names_regex += r'|'
            unit_names_regex += regex_escape_str(unit_name)
        unit_names_regex += ')'

        return unit_names_regex

    def _split_date_format(self, date_format:str, nicknames_set:set):
        """
        Takes a format in a string and splits it inclusively.

        For example, it will turn ":Day:Month:Year:" into
            [":", "Day", ":", "Month", ":", "Year", ":"] (assuming you have defined
            units with the names "Day", "Month", and "Year") and return it.
        """
        self._check_compiled()
        unit_names_regex = self._get_names_regex(nicknames_set)
        return split_inclusive(unit_names_regex, date_format)

    def _check_compiled(self):
        assert self._compiled, 'You must compile the TimeSystem before using it.'

    def _unit_for_unit_name(self, unit_name:str):
        assert unit_name in self._units_by_name, f'There is no defined Unit in the {self.name} TimeSystem with the name \"{unit_name}\"'
        return self._units_by_name[unit_name]

    def _exact_div_for_exact_div_name(self, div_name:str):
        assert div_name in self._exact_divs_by_name, f'There is no defined ExactDivision in the {self.name} TimeSystem with the name \"{div_name}\"'
        return self._exact_divs_by_name[div_name]

    def _repeating_div_for_repeating_div_name(self, div_name:str):
        assert div_name in self._repeating_divs_by_name, f'There is no defined RepeatingDivision in the {self.name} TimeSystem with the name \"{div_name}\"'
        return self._repeating_divs_by_name[div_name]

    def _exception_for_exception_name(self, exception_name:str):
        assert exception_name in self._exceptions_by_name, f'There is no defined TimeException in the {self.name} TimeSystem with the name \"{exception_name}\"'
        return self._exceptions_by_name[exception_name]

    def _get_exact_div_offsets(self, date_in_base_unit, div_name):
        """
        Returns the names of the subdivisions of the ExactDivision
            ("January", "February", "March", etc.) and the offsets that apply
            to get to each one.
        """
        div = self._exact_div_for_exact_div_name(div_name)
        unit_dividing = self._unit_for_unit_name(div.name_of_unit_dividing)
        unit_dividing_into = self._unit_for_unit_name(div.name_of_unit_dividing_into)
        div_cs = div.div_corrections
        offset_names = []
        offsets = []
        exceptions_used = []

        for div_def in div.div_defs:
            offset_names.append(div_def[0])
            offsets.append(unit_dividing_into.to_base(div_def[1]))

        for div_c in div_cs:
            exception = self._exception_for_exception_name(div_c[0])

            # Check if exception applies for given date
            interval_unit = self._unit_for_unit_name(exception.interval_amount_unit_name)
            interval_amt = int(exception.interval_amount)

            # If applies, then add the time
            if (0 == (int(interval_unit.from_base(date_in_base_unit)) % interval_amt)):
                add_amt_unit = self._unit_for_unit_name(exception.add_amount_unit_name)

                for i in range(len(offset_names)):
                    if offset_names[i] == div_c[1]:
                        offsets[i] += add_amt_unit.to_base(exception.add_amount)

        return offset_names, offsets

    def _check_formats_same(self, split_num_format, other_format, nicknames_set):
        """
        This format checks that two formats, one with numbers and the other
            without, are the same
        """
        if len(split_num_format) != len(other_format):
            return False

        for num_str, other_str in zip(split_num_format, other_format):
            try:
                Decimal(num_str)
                continue
            except InvalidOperation:
                # Then num_str is not a Decimal, so either stands for a nickname
                #   or is a delimiter
                if num_str in nicknames_set:
                    # its a nickname like Mon., Tue., Wed., etc. so no different
                    #   than if it were a number
                    continue

                # It's a delimiter, so make sure that they are the same delimiters
                if num_str != other_str:
                    return False
        return True

    # -------------------------------------------------------------------------
    # Helper Classes

    class TimeException:
        def __init__(self, name:str, interval_amount:Decimal, interval_amount_unit_name:str, add_amount:Decimal, add_amount_unit_name:str):
            super().__init__()

            assert interval_amount > 0, 'The interval that causes time to be added must be greater than 0.'

            interval_amount = confirm_is_type_decimal(interval_amount)
            add_amount = confirm_is_type_decimal(add_amount)

            self.name = name
            self.interval_amount = interval_amount # amount of time till this exception comes into affect
            self.interval_amount_unit_name = interval_amount_unit_name # the name of the unit that the inteval amount is in
            self.add_amount = add_amount # how much time to add every time interval happens (can be negative)
            self.add_amount_unit_name = add_amount_unit_name

        def __repr__(self):
            return f'{self.__class__.__name__}(Every {self.interval_amount} {self.interval_amount_unit_name}(s), add {self.add_amount} {self.add_amount_unit_name}(s))'

    class ExactDivision:
        """
        An ExactDivision takes a Unit and divides it into smaller pieces exactly.
            For example, a Year can be divided into Months, and Months are
            defined in Days. You may be tempted to just make them Units,
            but then they will be averaged to about 30 days each and you
            cannot label them as January, February, March, etc. so this is
            what you should use if you want to label each division.
        """

        def __init__(self, name:str, name_of_unit_dividing:str, name_of_unit_dividing_into:str, division_defs:list, division_corrections:list):
            """
            division_defs should be in form
                [("Name", int duration), ("January", 31), ("February", 28),("March", 31), ...]
                and define what each division's name is as well as how many of
                the unit_dividing_into it takes up. So January takes 31 Days.

            division_corrections should be in form:
                [("Name of TimeException", "Name of division_def to fix when exception occurs"),
                 ("Leap Year 4", "February"), ("Leap Year 100", "February"), ("Leap Year 400", "February")]

                and is so that divisions can be fixed when a TimeException occurs,
                adding or subtracting time from the unit the ExactDivision is
                dividing. For example, there is a TimeException that says
                that every 4 years, a Day is added. What is that one Day added
                to? February, so you need to say that.
            """
            assert name is not None, "Every ExactDivision must have a name. It cannot have a Null (None) name."
            assert name_of_unit_dividing is not None, "Every ExactDivision must have a name_of_unit_dividing. It cannot be Null (None)."
            assert name_of_unit_dividing_into is not None, "Every ExactDivision must have a name_of_unit_dividing_into. It cannot be Null (None)."
            assert division_defs is not None, "Every ExactDivision must have division_defs not be None."
            assert len(division_defs) >= 2, "Every ExactDivision must at least divide their Unit into 2. {name} does not. You need to add more defs to division_defs."
            assert division_corrections is not None, "Every ExactDivision must have division_defs not be None. It should be at least an empty list []."

            for div_def in division_defs:
                assert (len(div_def) == 2) and isinstance(div_def[0], str) \
                        and isinstance(div_def[1], int), \
                        f'{div_def} in {name} must be in format (str, int)'

            for div_c in division_corrections:
                assert (len(div_c) == 2) and isinstance(div_c[0], str) \
                        and isinstance(div_c[1], str), \
                        f'{div_c} in {name} must be in format (str, str)'

            self.name = name
            self.name_of_unit_dividing = name_of_unit_dividing # This would be Years if dividing Years into Months
            self.name_of_unit_dividing_into = name_of_unit_dividing_into # This would be Days if dividing Years into Months
            self.div_defs = division_defs
            self.div_corrections = division_corrections

        def name_in_division_defs(self, name:str):
            """
            Returns True if the given name is the name of a subdivision
                (like "January", "February", "March", etc.) defined by this
                ExactDivision and False otherwise.
            """
            found = False
            for div_def in self.div_defs:
                if div_def[0] == name:
                    found = True
                    break

            return found

        def name_in_div_corrections(self, name:str):
            """
            Returns true if the given name is the name of a TimeException whose
                add_amount is accounted for and False otherwise.
            """
            found = False
            for div_c in self.div_corrections:
                if div_c[0] == name:
                    found = True
                    break

            return found

        def __repr__(self):
            return f'{self.__class__.__name__}(name={self.name})'

    class RepeatingDivision(ExactDivision):
        """
        A RepeatingDivision is something like a Week that just repeats endlessly
            without having to fit into another Unit like a Year exactly.
        """
        def __init__(self, name:str, name_of_unit_in:str, division_defs:list):
            """
            division_defs are in form
                [(div_name:str, number of unit in it takes up:int or Decimal),
                    ("Monday", 1), ("Tuesday", 1), etc.]
            """
            super().__init__()
            assert name is not None, f"Every {self.__class__.__name__} must have a name."
            assert name_of_unit_in is not None, f"Every {self.__class__.__name__} must have a unit that it is in. For example, a Week is in Days."
            self.name = name
            self.name_of_unit_in = name_of_unit_in
            self.division_defs = division_defs

            # Figure out the total time for a repetition. For Example, a Week
            #   repeats every 7 days
            self.repetition_time = 0
            for div_def in division_defs:
                self.repetition_time += div_def[1]

        def __repr__(self):
            return f'{self.__class__.__name__}(name={self.name})'

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
    print("__Unit_Conversion_With_Time_Exceptions__")

    # Add the exceptions that make the Gregorian Calander work
    LEAP_DAY_4 = "Leap Day 4"
    LEAP_DAY_100 = "Leap Day 100"
    LEAP_DAY_400 = "Leap Day 400"
    greg_calander.add_exception(LEAP_DAY_4, 4, 'Year', 1, 'Day') # Every 4 Years, add 1 Day
    greg_calander.add_exception(LEAP_DAY_100, 100, 'Year', -1, 'Day') # Every 100 Years, add -1 Day to get rid of leap year
    greg_calander.add_exception(LEAP_DAY_400, 400, 'Year', 1, 'Day') # Every 400 Years, add 1 Day to add leap year back

    greg_calander.compile()

    year_in_sec = test_unit_to_base(1, 'Year')
    assert year_in_sec == 31556952, 'Conversion from Years to Seconds is Wrong.'
    assert test_base_to_unit(year_in_sec, 'Year') == 1, 'For some reason, the conversion back to Years is wrong'

    day_in_sec = test_unit_to_base(1, 'Day')

    test_base_to_unit(test_unit_to_base(1, 'Year'), 'Year')

    print("")
    print("__Base_To_Format__")

    def base_to_format_test(date_in_base, date_format, desired_date_format_result, neg_date_format:str=None, one_based_units=None, nicknames:dict=None):
        in_base_format = greg_calander.base_to_format(date_in_base, date_format, one_based_units=one_based_units, neg_date_format=neg_date_format, nicknames=nicknames)
        print(f'{date_in_base} Second(s) = {in_base_format} ({date_format})')
        assert in_base_format == desired_date_format_result, f'Result was wrong. The result was "{in_base_format}" but should be "{desired_date_format_result}".'
        return in_base_format

    base_to_format_test(year_in_sec, ':Year:Day:Second:', ':1:0:0:')
    base_to_format_test(year_in_sec + 1, ':Year:Day:Second:', ':1:0:1:')
    base_to_format_test(year_in_sec + day_in_sec, ':Year:Day:Second:', ':1:1:0:')
    base_to_format_test(year_in_sec + (day_in_sec * 100) + 1, ':Year:Day:Second:', ':1:100:1:')
    base_to_format_test((year_in_sec * 2021) + (day_in_sec * 21) + 1, ':Year:Day:Second:', ':2021:21:1:')

    print("")
    print("__Format_To_Base__")

    def format_to_base_test(date_in_format, date_format, desired_date_result, origional_date_in_base_unit=0, one_based_units=None, nicknames=None, neg_date_format=None):
        in_base_unit = greg_calander.format_to_base(date_in_format, date_format, origional_date_in_base_unit, one_based_units=one_based_units, nicknames=nicknames, neg_date_format=neg_date_format)
        print(f'({date_format}) {date_in_format} = {int(in_base_unit)} {greg_calander._base_unit.name}(s)')
        assert in_base_unit == desired_date_result, f'Date in base unit is wrong. Should be: {desired_date_result}. ({date_in_format} in {date_format}) {f"origional_date_in_base_unit: {origional_date_in_base_unit}" if origional_date_in_base_unit == 0 else ""}.'
        return in_base_unit

    format_to_base_test(':2021:21:1:', ':Year:Day:Second:', (year_in_sec * 2021) + (day_in_sec * 21) + 1)
    format_to_base_test('-:2021:21:1:', ':Year:Day:Second:', -((year_in_sec * 2021) + (day_in_sec * 21) + 1), neg_date_format='-:Year:Day:Second:')

    # Define Month
    FEBRUARY = 'February'
    greg_calander.add_exact_division("Month", "Year", "Day",
            [
                ('January', 31),   (FEBRUARY, 28), ('March', 31),    ('April', 30),
                ('May', 31),       ('June', 30),     ('July', 31),     ('August', 31),
                ('Septemder', 30), ('October', 31),  ('November', 30), ('December', 31)
            ],
            [
                (LEAP_DAY_4, FEBRUARY), (LEAP_DAY_100, FEBRUARY), (LEAP_DAY_400, FEBRUARY)
            ])
    greg_calander.compile()

    ONE_BASED_UNITS = ["Month", "Day", "Week"]

    AMERICAN_FORMAT = 'Month/Day/Year'
    in_base = format_to_base_test('6/26/2021', AMERICAN_FORMAT, 63791806392, one_based_units=ONE_BASED_UNITS)
    base_to_format_test(in_base, AMERICAN_FORMAT, '6/26/2021', one_based_units=ONE_BASED_UNITS)

    print("")
    print("__Leap_Years__")

    in_base = format_to_base_test('2/29/2020', AMERICAN_FORMAT, 63750140640, one_based_units=ONE_BASED_UNITS)
    base_to_format_test(in_base, AMERICAN_FORMAT, '2/29/2020', one_based_units=ONE_BASED_UNITS)

    in_base = format_to_base_test('2/29/2100', AMERICAN_FORMAT, 66274696800, one_based_units=ONE_BASED_UNITS)
    base_to_format_test(in_base, AMERICAN_FORMAT, '3/1/2100', one_based_units=ONE_BASED_UNITS)

    in_base = format_to_base_test('2/29/2400', AMERICAN_FORMAT, 75741782400, one_based_units=ONE_BASED_UNITS)
    base_to_format_test(in_base, AMERICAN_FORMAT, '2/29/2400', one_based_units=ONE_BASED_UNITS)

    print("")
    print("__Weeks__")

    greg_calander.add_repeating_division('Week', 'Day', [
            ('Sunday', 1), ('Monday', 1), ('Tuesday', 1), ('Wednesday', 1),
            ('Thursday', 1), ('Friday', 1), ('Saturday', 1)
        ])
    greg_calander.compile()

    NICKNAMES = \
        {
            'wk': {
                'nick_for': 'Week',
                'names': {
                    0: 'Sun.',
                    1: 'Mon.',
                    2: 'Tue.',
                    3: 'Wed.',
                    4: 'Thu.',
                    5: 'Fri.',
                    6: 'Sat.',
                }
            },
            'mn': {
                'nick_for': 'Month',
                'names': {
                    0: 'Jan.',
                    1: 'Feb.',
                    2: 'Mar.',
                    3: 'Apr.',
                    4: 'May.',
                    5: 'Jun.',
                    6: 'Jul.',
                    7: 'Aug.',
                    8: 'Sep.',
                    9: 'Oct.',
                    10:'Nov.',
                    11:'Dec.'
                }
            },
            'MN': {
                'nick_for': 'Month',
                'names': {
                    0: 'January',
                    1: 'February',
                    2: 'March',
                    3: 'April',
                    4: 'May',
                    5: 'June',
                    6: 'July',
                    7: 'August',
                    8: 'September',
                    9: 'October',
                    10:'November',
                    11:'December'
                }
            }
        }


