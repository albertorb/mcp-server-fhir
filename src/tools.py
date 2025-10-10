"""MCP tool definitions and response formatters for Epic FHIR data."""

from mcp.types import Tool

# Tool definitions for MCP protocol
EPIC_FHIR_TOOLS = [
    Tool(
        name="get_patient",
        description="Get patient demographics and basic information by FHIR ID",
        inputSchema={
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "string",
                    "description": "FHIR patient ID (e.g., erXuFYUfucBZaryVksYEcMg3)",
                }
            },
            "required": ["patient_id"],
        },
    ),
    Tool(
        name="search_patients",
        description="Search for patients by demographics (name, birthdate, gender)",
        inputSchema={
            "type": "object",
            "properties": {
                "family": {"type": "string", "description": "Family name (last name)"},
                "given": {"type": "string", "description": "Given name (first name)"},
                "birthdate": {
                    "type": "string",
                    "description": "Birth date in YYYY-MM-DD format",
                },
                "gender": {
                    "type": "string",
                    "enum": ["male", "female", "other", "unknown"],
                    "description": "Patient gender",
                },
            },
        },
    ),
    Tool(
        name="get_patient_conditions",
        description="Get patient's medical conditions, diagnoses, and health problems",
        inputSchema={
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "string",
                    "description": "FHIR patient ID",
                }
            },
            "required": ["patient_id"],
        },
    ),
    Tool(
        name="get_patient_medications",
        description="Get patient's current and past medications and prescriptions",
        inputSchema={
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "string",
                    "description": "FHIR patient ID",
                }
            },
            "required": ["patient_id"],
        },
    ),
    Tool(
        name="get_patient_observations",
        description="Get patient's clinical observations (labs, vitals, etc.)",
        inputSchema={
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "string",
                    "description": "FHIR patient ID",
                },
                "category": {
                    "type": "string",
                    "enum": ["vital-signs", "laboratory", "imaging", "social-history"],
                    "description": "Filter by observation category",
                },
            },
            "required": ["patient_id"],
        },
    ),
    Tool(
        name="get_patient_allergies",
        description="Get patient's allergies and adverse reactions",
        inputSchema={
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "string",
                    "description": "FHIR patient ID",
                }
            },
            "required": ["patient_id"],
        },
    ),
    Tool(
        name="get_patient_immunizations",
        description="Get patient's vaccination and immunization history",
        inputSchema={
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "string",
                    "description": "FHIR patient ID",
                }
            },
            "required": ["patient_id"],
        },
    ),
    Tool(
        name="get_patient_procedures",
        description="Get patient's medical and surgical procedures",
        inputSchema={
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "string",
                    "description": "FHIR patient ID",
                }
            },
            "required": ["patient_id"],
        },
    ),
]


def format_patient_response(data: dict) -> str:
    """Format patient FHIR resource for LLM consumption.

    Args:
        data: FHIR Patient resource

    Returns:
        Formatted patient information string
    """
    if not data or "resourceType" not in data:
        return "No patient data found."

    # Extract name
    name = data.get("name", [{}])[0]
    given = " ".join(name.get("given", []))
    family = name.get("family", "Unknown")
    full_name = f"{given} {family}".strip()

    # Build response
    result = [
        f"**Patient: {full_name}**",
        f"FHIR ID: {data.get('id', 'unknown')}",
        f"Gender: {data.get('gender', 'unknown').capitalize()}",
        f"Birth Date: {data.get('birthDate', 'unknown')}",
    ]

    # Add contact info if available
    if telecom := data.get("telecom"):
        for contact in telecom:
            system = contact.get("system", "").capitalize()
            value = contact.get("value", "")
            if system and value:
                result.append(f"{system}: {value}")

    # Add address if available
    if addresses := data.get("address"):
        addr = addresses[0]
        lines = addr.get("line", [])
        city = addr.get("city", "")
        state = addr.get("state", "")
        postal = addr.get("postalCode", "")
        if lines or city:
            addr_str = ", ".join(filter(None, [*lines, city, state, postal]))
            result.append(f"Address: {addr_str}")

    return "\n".join(result)


def format_bundle_response(bundle: dict, resource_type: str) -> str:
    """Format FHIR bundle response for LLM consumption.

    Args:
        bundle: FHIR Bundle resource
        resource_type: Type of resources in bundle

    Returns:
        Formatted bundle information string
    """
    if not bundle.get("entry"):
        return f"No {resource_type} found."

    total = bundle.get("total", len(bundle.get("entry", [])))
    entries = bundle.get("entry", [])

    result = [f"**Found {total} {resource_type}(s)**\n"]

    for i, entry in enumerate(entries, 1):
        resource = entry.get("resource", {})
        formatted = format_resource(resource, resource_type)
        result.append(f"{i}. {formatted}")

    return "\n".join(result)


def format_resource(resource: dict, resource_type: str) -> str:
    """Format individual FHIR resource based on type.

    Args:
        resource: FHIR resource
        resource_type: Type of resource

    Returns:
        Formatted resource string
    """
    if resource_type == "Patient":
        name = resource.get("name", [{}])[0]
        given = " ".join(name.get("given", []))
        family = name.get("family", "")
        return f"{given} {family} (ID: {resource.get('id')})"

    elif resource_type == "Condition":
        code_text = resource.get("code", {}).get("text", "Unknown condition")
        clinical_status = (
            resource.get("clinicalStatus", {}).get("coding", [{}])[0].get("code", "unknown")
        )
        onset = resource.get("onsetDateTime", resource.get("onsetString", ""))
        if onset and "T" in onset:
            onset = onset.split("T")[0]
        return f"{code_text} | Status: {clinical_status}" + (f" | Onset: {onset}" if onset else "")

    elif resource_type == "MedicationRequest":
        med_text = resource.get("medicationCodeableConcept", {}).get("text", "Unknown medication")
        status = resource.get("status", "unknown")
        dosage = ""
        if dosage_inst := resource.get("dosageInstruction"):
            dosage = dosage_inst[0].get("text", "")
        return f"{med_text} | Status: {status}" + (f" | Dosage: {dosage}" if dosage else "")

    elif resource_type == "Observation":
        code_text = resource.get("code", {}).get("text", "Unknown observation")
        value_str = "No value"

        if value_qty := resource.get("valueQuantity"):
            value_str = f"{value_qty.get('value')} {value_qty.get('unit', '')}"
        elif value_str_raw := resource.get("valueString"):
            value_str = value_str_raw
        elif value_bool := resource.get("valueBoolean"):
            value_str = str(value_bool)

        date = resource.get("effectiveDateTime", "")
        if date and "T" in date:
            date = date.split("T")[0]

        return f"{code_text}: {value_str}" + (f" | Date: {date}" if date else "")

    elif resource_type == "AllergyIntolerance":
        substance = resource.get("code", {}).get("text", "Unknown substance")
        reaction_text = ""

        if reactions := resource.get("reaction"):
            manifestations = reactions[0].get("manifestation", [])
            if manifestations:
                reaction_text = " → " + manifestations[0].get("text", "")

        severity = resource.get("criticality", "")
        return f"{substance}{reaction_text}" + (f" | Severity: {severity}" if severity else "")

    elif resource_type == "Immunization":
        vaccine = resource.get("vaccineCode", {}).get("text", "Unknown vaccine")
        date = resource.get("occurrenceDateTime", "Unknown date")
        if "T" in date:
            date = date.split("T")[0]
        status = resource.get("status", "")
        return f"{vaccine} | Date: {date}" + (f" | Status: {status}" if status else "")

    elif resource_type == "Procedure":
        proc_text = resource.get("code", {}).get("text", "Unknown procedure")
        status = resource.get("status", "")
        date = resource.get("performedDateTime", resource.get("performedPeriod", {}).get("start", ""))
        if date and "T" in date:
            date = date.split("T")[0]
        return f"{proc_text} | Status: {status}" + (f" | Date: {date}" if date else "")

    else:
        return f"Resource ID: {resource.get('id', 'Unknown')}"
