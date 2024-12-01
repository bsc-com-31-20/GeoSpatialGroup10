# -*- coding: utf-8 -*-
import os
import json  # Import the JSON module
from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from qgis.core import QgsProject, QgsVectorLayer
from qgis.PyQt.QtCore import pyqtSlot
from PyQt5.QtWidgets import QMessageBox
import psycopg2  # Import for database connection
from qgis.core import QgsWkbTypes


# This loads your .ui file so that PyQt can populate your plugin with the elements from Qt Designer
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'floods_dialog_base.ui'))


class FloodsDialog(QtWidgets.QDialog, FORM_CLASS):
    
    def __init__(self, parent=None):
        """Constructor."""
        super(FloodsDialog, self).__init__(parent)
        self.setupUi(self)

        # Populate combo boxes with vector layers
        self.populate_layer_comboboxes()

        # Connect button click to save layers to the database
        self.saveToDBButton.clicked.connect(self.save_layers_to_db)
        self.runBufferButton.clicked.connect(self.run_buffer_analysis)

    def populate_layer_comboboxes(self):
        """Populate combo boxes with available vector layers in the QGIS project."""
        self.layerComboBox1.clear()  # Ensure combo boxes are reset
        self.layerComboBox2.clear()

        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if isinstance(layer, QgsVectorLayer):
                self.layerComboBox1.addItem(layer.name(), layer.id())
                self.layerComboBox2.addItem(layer.name(), layer.id())

    @pyqtSlot()
    def save_layers_to_db(self):
        """Save selected layers' attributes to the PostGIS database."""
        layer1_id = self.layerComboBox1.currentData()
        layer2_id = self.layerComboBox2.currentData()

        if not layer1_id or not layer2_id:
            QMessageBox.warning(self, "Input Error", "Please select two valid layers.")
            return

        # Retrieve selected layers
        layer1 = QgsProject.instance().mapLayer(layer1_id)
        layer2 = QgsProject.instance().mapLayer(layer2_id)

        if not (layer1 and layer2):
            QMessageBox.warning(self, "Error", "Could not retrieve selected layers.")
            return

        try:
            # Call a function to save attributes to the database
            save_attributes_to_postgis(layer1, layer2)
            QMessageBox.information(self, "Success", "Layers saved to the database successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save layers: {e}")

    def run_buffer_analysis(self):
        """Perform buffer analysis on the river dataset in the database."""
        try:
            # Get the buffer distance from the user
            buffer_distance = self.bufferDistanceLineEdit.text()
            if not buffer_distance.isdigit():
                QMessageBox.warning(self, "Input Error", "Buffer distance must be a positive number.")
                return

            # Convert to numeric type
            buffer_distance = float(buffer_distance) * 0.001

            # Call a function to perform buffer analysis
            perform_buffer_analysis(buffer_distance)
            QMessageBox.information(self, "Success", "Buffer analysis completed and merged with enumeration data!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Buffer analysis failed: {e}")


def save_attributes_to_postgis(layer1, layer2):
    """Save the attributes of the given layers to the PostGIS database."""
    # Database connection parameters
    db_params = {
        "dbname": "g10",
        "user": "postgres",
        "password": "3269183",
        "host": "localhost",
        "port": 5432,
    }

    # Connect to the database
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()

    # Save attributes of layer1
    # For river dataset
    save_layer_attributes(cursor, layer1, "river_dataset", "river")

# For enumeration dataset
    save_layer_attributes(cursor, layer2, "enumeration_dataset", "enumeration")


    # Save attributes of layer2

    # Commit changes and close connection
    conn.commit()
    cursor.close()
    conn.close()


def save_layer_attributes(cursor, layer, table_name, dataset_type):
    """Save attributes of a layer to a specific PostGIS table with separate columns for each attribute and geometry column."""
    # Set geometry type based on dataset type
    if dataset_type == "river":
        geometry_type = "MULTILINESTRING"
    elif dataset_type == "enumeration":
        geometry_type = "MULTIPOLYGON"
    else:
        raise ValueError("Unknown dataset type. Supported types are 'river' and 'enumeration'.")

    # Get the CRS EPSG code
    authid = layer.crs().authid()
    if ":" in authid:
        crs_epsg = authid.split(":")[1]
    else:
        raise ValueError(f"Layer CRS '{authid}' does not contain an EPSG code.")

    # Get the field names and types from the layer
    fields = layer.fields()
    field_names = [field.name() for field in fields]
    field_types = {
        'Integer': 'INTEGER',
        'Real': 'DOUBLE PRECISION',
        'String': 'TEXT',
        'Date': 'DATE',
        'Time': 'TIME',
        'DateTime': 'TIMESTAMP'
    }

    # Create table with separate columns for each attribute and a geometry column
    create_table_query = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id SERIAL PRIMARY KEY,
            geom GEOMETRY({geometry_type}, {crs_epsg})  -- Geometry column
        """
    for field in fields:
        postgres_type = field_types.get(field.typeName(), 'TEXT')  # Default to TEXT for unknown types
        create_table_query += f", {field.name()} {postgres_type}"
    create_table_query += ");"
    cursor.execute(create_table_query)

    # Insert attributes and geometry into the table
    for feature in layer.getFeatures():
        geom = feature.geometry()
        if not geom.isMultipart() and geometry_type.startswith("MULTI"):
            geom = geom.convertToMultiType()  # Convert single-part geometry to multi-part

        geom_wkt = geom.asWkt()  # Extract geometry as WKT
        values = [f"ST_GeomFromText('{geom_wkt}', {crs_epsg})"]  # Geometry value
        for attr in feature.attributes():
            # Convert QVariant to a PostgreSQL-compatible value
            if attr is None:
                values.append("NULL")
            elif isinstance(attr, str):
                values.append(f"'{attr.replace('\'', '\'\'')}'")  # Escape single quotes in strings
            else:
                values.append(str(attr))

        # Build and execute the insert query
        insert_query = f"""
            INSERT INTO {table_name} (geom, {', '.join(field_names)})
            VALUES ({', '.join(values)});
        """
        cursor.execute(insert_query)

    # Add a spatial index to the geometry column for performance
    cursor.execute(f"CREATE INDEX IF NOT EXISTS {table_name}_geom_idx ON {table_name} USING GIST (geom);")

#Ukuku kuli ntchito
#eh

def perform_buffer_analysis(buffer_distance):
    """Perform buffer analysis on the river dataset and intersect with enumeration data."""
    # Database connection parameters
    db_params = {
        "dbname": "g10",
        "user": "postgres",
        "password": "3269183",
        "host": "localhost",
        "port": 5432,
    }

    # Connect to the database
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()

    # Step 1: Create buffer around the river dataset
    buffer_query = f"""
        DROP TABLE IF EXISTS river_buffer;
        CREATE TABLE river_buffer AS
        SELECT
            id,  -- Retain the original ID
            ST_Buffer(geom, {buffer_distance}) AS geom  -- Create buffer geometry
        FROM river_dataset;
    """
    cursor.execute(buffer_query)

    # Add spatial index to the buffer table
    cursor.execute("CREATE INDEX ON river_buffer USING GIST (geom);")

    # Step 2: Perform intersection with enumeration dataset
    intersection_query = f"""
        DROP TABLE IF EXISTS intersection_output;
        CREATE TABLE intersection_output AS
        SELECT
            a.id AS buffer_id,
            b.id AS enum_id,
            ST_Intersection(a.geom, b.geom) AS geom  -- Compute intersection geometry
        FROM river_buffer AS a
        JOIN enumeration_dataset AS b
        ON ST_Intersects(a.geom, b.geom);
    """
    cursor.execute(intersection_query)

    # Add spatial index to the intersection output table
    cursor.execute("CREATE INDEX ON intersection_output USING GIST (geom);")

    # Commit and close the connection
    conn.commit()
    cursor.close()
    conn.close()
