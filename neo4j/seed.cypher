// Seed Core Industrial Attributes
MERGE (a1:Attribute {id: 'voltage', name: 'Rated Voltage', category: 'electrical', unit_type: 'voltage', default_unit: 'V'})
MERGE (a2:Attribute {id: 'power', name: 'Rated Power', category: 'performance', unit_type: 'power', default_unit: 'kW'})
MERGE (a3:Attribute {id: 'pressure', name: 'Max Operating Pressure', category: 'hydraulic', unit_type: 'pressure', default_unit: 'bar'})
MERGE (a4:Attribute {id: 'flow_rate', name: 'Flow Rate', category: 'hydraulic', unit_type: 'flow', default_unit: 'L/min'})
MERGE (a5:Attribute {id: 'rotational_speed', name: 'Rotational Speed', category: 'performance', unit_type: 'rotational_speed', default_unit: 'RPM'})
MERGE (a6:Attribute {id: 'temperature', name: 'Operating Temperature', category: 'environmental', unit_type: 'temperature', default_unit: '°C'})
MERGE (a7:Attribute {id: 'weight', name: 'Weight', category: 'physical', unit_type: 'mass', default_unit: 'kg'});
