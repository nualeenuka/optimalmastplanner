# -*- coding: utf-8 -*-
"""
/***************************************************************************
 OptimalMeasurementPlanner
                                 A QGIS plugin
                             -------------------
        begin                : 2025-04-15
        copyright            : (C) 2025 by Nualee
        email                : nalni@vestas.com
 ***************************************************************************/
This plugin provides tools for optimal placement and analysis of meteorological
masts and wind turbines.
It processes TRIX files, generates spatial outputs, and supports visualization
and reporting in QGIS.

This script initializes the plugin, making it known to QGIS.
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load OptimalMeasurementPlanner class from file OptimalMeasurementPlanner.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .OptimalMeasurementPlanner import OptimalMeasurementPlanner
    return OptimalMeasurementPlanner(iface)
