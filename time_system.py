from decimal import Decimal


class TimeSystem:
    def __init__(self, name):
        super().__init__()
        self.name = name

        self._units = []
        self._exceptions = []
        self._compiled = False

    # -------------------------------------------------------------------------
    # General Methods


    def unit_for_unit_name(self, unit_name:str):
        assert unit_name in self._units_by_name, f'There is no defined unit in the {self.name} TimeSystem with the name \"{unit_name}\"'
        return self._units_by_name[unit_name]

    def unit_to_base_unit(self, date_in_unit:Decimal, unit_name):
        self._check_compiled()

        if not isinstance(date_in_unit, Decimal):
            date_in_unit = Decimal(date_in_unit)

        unit = self.unit_for_unit_name(unit_name)
        return unit.to_base(date_in_unit)

    def base_unit_to_unit(self, date_in_base_unit:Decimal, unit_name):
        self._check_compiled()

        if not isinstance(date_in_base_unit, Decimal):
            date_in_base_unit = Decimal(date_in_base_unit)

        unit = self.unit_for_unit_name(unit_name)
        return unit.from_base(date_in_base_unit)

    def add_unit(self, name, conversion_factor:Decimal=Decimal(1), parent_unit_name:str=None):
        assert not (name in [u.name for u in self._units]), 'You cannot have two units with the same name in the TimeSystem.'
        self._units.append(self.Unit(name, conversion_factor, parent_unit_name))
        self._compiled = False

    def add_exception(self, interval_amount:Decimal, interval_amount_unit_name:str, add_amount:Decimal, add_amount_unit_name:str):
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

            if not isinstance(interval_amount, Decimal):
                interval_amount = Decimal(interval_amount)

            if not isinstance(add_amount, Decimal):
                add_amount = Decimal(add_amount)

            self.interval_amount = interval_amount # amount of time till this exception comes into affect
            self.interval_amount_unit_name = interval_amount_unit_name # the name of the unit that the inteval amount is in
            self.add_amount = add_amount # how much time to add every time interval happens (can be negative)
            self.add_amount_unit_name = add_amount_unit_name

        def __repr__(self):
            return f'TimeException(Every {self.interval_amount} {self.interval_amount_unit_name}(s), add {self.add_amount} {self.add_amount_unit_name}(s))'

    class Unit:
        def __init__(self, name:str, conversion_factor:Decimal=Decimal(1), parent_unit_name:str=None):
            super().__init__()
            if not isinstance(conversion_factor, Decimal):
                conversion_factor = Decimal(conversion_factor)
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

        def to_base(self, date_in_this_unit):
            """
            Converts the number in this unit to the base unit of this TimeSystem.
            """
            parent = self.get_parent_unit()
            return date_in_this_unit if parent is None else parent.to_base(date_in_this_unit) * self.get_working_conversion_factor()

        def from_base(self, date_in_base_unit):
            """
            Converts the number in base unit to this unit of this TimeSystem.
            """
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

    # Add the exceptions that make the Gregorian Calander work
    greg_calander.add_exception(4, 'Year', 1, 'Day') # Every 4 Years, add 1 Day
    greg_calander.add_exception(100, 'Year', -1, 'Day') # Every 100 Years, add -1 Day to get rid of leap year
    greg_calander.add_exception(400, 'Year', 1, 'Day') # Every 400 Years, add 1 Day to add leap year back

    greg_calander.compile()

    year_in_sec = test_unit_to_base(1, 'Year')
    assert year_in_sec == 31556952, 'Conversion from Years to Seconds is Wrong.'
    assert test_base_to_unit(year_in_sec, 'Year') == 1, 'For some reason, the conversion back to Years is wrong'

    test_base_to_unit(test_unit_to_base(1, 'Year'), 'Year')


