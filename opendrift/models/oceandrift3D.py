# This file is part of OpenDrift.
#
# OpenDrift is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 2
#
# OpenDrift is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OpenDrift.  If not, see <http://www.gnu.org/licenses/>.
#
# Copyright 2015, Knut-Frode Dagestad, MET Norway

import numpy as np
from opendrift.models.opendrift3D import OpenDrift3DSimulation
from opendrift.elements.passivetracer import PassiveTracer

# We add the property 'wind_drift_factor' to the element class
PassiveTracer.variables = PassiveTracer.add_variables([
                            ('wind_drift_factor', {'dtype': np.float32,
                                                   'unit': '%',
                                                   'default': 0.0}),
                            ('age_seconds', {'dtype': np.float32,
                                             'units': 's',
                                             'default': 0})])


class OceanDrift3D(OpenDrift3DSimulation):
    """Trajectory model based on the OpenDrift framework.

    Simply propagation with horizontal and vertical ocean currents
    and possibly additional wind drag.
    Suitable for passive tracers, e.g. for tracking water particles.
    Developed at MET Norway.

    """

    ElementType = PassiveTracer
    required_variables = ['x_sea_water_velocity',
                          'y_sea_water_velocity',
                          'x_wind', 'y_wind',
                          'upward_sea_water_velocity',
                          'ocean_vertical_diffusivity',
                          'sea_floor_depth_below_sea_level'
                          ]

    required_variables.append('land_binary_mask')

    required_profiles = ['ocean_vertical_diffusivity']
    # The depth range (in m) which profiles shall cover
    required_profiles_z_range = [-120, 0]

    fallback_values = {'x_sea_water_velocity': 0,
                       'y_sea_water_velocity': 0,
                       'x_wind': 0,
                       'y_wind': 0,
                       'upward_sea_water_velocity': 0,
                       'ocean_vertical_diffusivity': 0.02,
                       'sea_floor_depth_below_sea_level': 10000
                       }

    configspec = '''
        [drift]
            scheme = option('euler', 'runge-kutta', default='euler')
            max_age_seconds = float(min=0, default=None)
        [processes]
            turbulentmixing = boolean(default=False)
            verticaladvection = boolean(default=True)
        [turbulentmixing]
            timestep = float(min=0.1, max=3600, default=1.)
            verticalresolution = float(min=0.01, max=10, default = 1.)
            diffusivitymodel = string(default='environment')
            '''

    def update_terminal_velocity(self):
        '''
        Terminal velocity due to buoyancy or sedimentation rate,
        to be used in turbulent mixing module.
        Using zero for passive particles, i.e. following water particles
        '''
        self.elements.terminal_velocity = 0.

    def update(self):
        """Update positions and properties of elements."""

        self.elements.age_seconds += self.time_step.total_seconds()

        # Simply move particles with ambient current
        self.advect_ocean_current()

        # Advect particles due to wind drag
        # (according to specified wind_drift_factor)
        self.advect_wind()

        # Turbulent Mixing
        if self.config['processes']['turbulentmixing'] is True:
            self.update_terminal_velocity()
            self.vertical_mixing()

        # Vertical advection
        if self.config['processes']['verticaladvection'] is True:
            self.vertical_advection()

        # Deactivate elements on land
        self.deactivate_elements(self.environment.land_binary_mask == 1,
                                 reason='stranded')

        # Deactivate elements that exceed a certain age
        if self.config['drift']['max_age_seconds'] is not None:
            self.deactivate_elements(self.elements.age_seconds >=
                                     self.config['drift']
                                     ['max_age_seconds'], reason='retired')