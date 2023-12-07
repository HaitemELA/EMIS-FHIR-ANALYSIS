import os
import requests
import json
import uuid

# Specify the root directory containing FHIR bundles (JSON files)
root_directory = r'C:\Users\Imtech\Downloads\EMIS'

# Specify the directory to store modified bundles
modified_bundles_directory = r'C:\Users\Imtech\Downloads\ModifiedBundles'

# Specify the base URL for the FHIR server
base_url = "http://localhost:52775/csp/healthshare/fhir/fhir/r3a/"

# Set headers for the request
headers = {
    'Accept': 'application/fhir+json',
    'Content-Type': 'application/fhir+json'
}

# Function to generate a GUID
def generate_guid():
    return str(uuid.uuid4())

# Function to handle description property
def handle_description(resource, prev_row_name):
    if 'description' in resource and not resource['description'].strip():
        # Replace empty 'description' with 'name' from the row above
        #resource['description'] = prev_row_name[0]
        resource['description'] = 'description'

# Function to handle title property
def handle_title(resource):
    if 'title' in resource and not resource['title'].strip():
        # Replace empty 'title'
        resource['title'] = 'title'

# Function to handle text property
def handle_text(resource):
    if 'text' in resource and not resource['text'].strip():
        # Replace empty 'title'
        resource['text'] = 'text'

def replace_empty_with_na_fhir(resource):
    if isinstance(resource, dict):
        for key, value in resource.items():
            if value in (None, ''):
                resource[key] = "N/A"
            #elif isinstance(value, (str, list, dict)):
            else:
                resource[key] = replace_empty_with_na_fhir(value)

        # Handle the 'text' property within the 'type' array
        if 'type' in resource and isinstance(resource['type'], list):
            for type_entry in resource['type']:
                if 'text' in type_entry and not type_entry['text'].strip():
                    type_entry['text'] = 'N/A'
                elif isinstance(resource['type'], dict) and 'text' in resource['type'] and not resource['type']['text'].strip():
                    resource['type']['text'] = 'N/A'

    elif isinstance(resource, list):
        resource = [replace_empty_with_na_fhir(element) if element is not None else "N/A" for element in resource]

    return resource


# Function to check and move HealthcareService reference for Observation resources
def check_and_move_healthcare_service(observation):
    if observation['resourceType'] == 'Observation':
        performer = observation.get('performer', [])
        healthcare_service_refs = [performer_ref.get('reference') for performer_ref in performer if 'HealthcareService' in performer_ref.get('reference', '')]

        if healthcare_service_refs:
            # Move HealthcareService reference to the comment property
            if 'comment' in observation:
                observation['comment'] += f'\n'.join(healthcare_service_refs)
            else:
                observation['comment'] = f'\n'.join(healthcare_service_refs)
            # Remove the reference from the performer property
            observation['performer'] = [performer_ref for performer_ref in performer if 'HealthcareService' not in performer_ref.get('reference', '')]

# Function to check and move HealthcareService reference for DiagnosticReport resources
def move_healthcare_service_reference(resource):
    if resource['resourceType'] == 'DiagnosticReport':
        # Check if 'performer' and 'actor' properties exist
        if 'performer' in resource: # and 'actor' in resource['performer']:
            performer = resource.get('performer', [])
            #print(performer)
            healthcare_service_refs = [performer_ref.get('actor').get('reference') for performer_ref in performer if 'HealthcareService' in performer_ref.get('actor', '').get('reference', '')]
            #print(healthcare_service_refs)
            if healthcare_service_refs:
                # Move HealthcareService reference to the comment property
                if 'conclusion' in resource:
                    resource['conclusion'] += f'\n'.join(healthcare_service_refs)
                else:
                    resource['conclusion'] = f'\n'.join(healthcare_service_refs)
                resource['performer'] = [performer_ref for performer_ref in performer if 'HealthcareService' not in performer_ref.get('actor', '').get('reference', '')]


# Function to handle MedicationRequest extension property
def handle_medication_request_extension(medication_request):
    extension = medication_request.get('extension', [])
    for ext in extension:
        handle_extension_recursive(ext)

# Recursive function to handle extensions at all levels
def handle_extension_recursive(extension):
    if 'url' in extension:
        if extension['url'] == 'https://fhir.nhs.uk/STU3/StructureDefinition/Extension-CareConnect-GPC-MedicationStatusReason-1':
            # Assuming the structure of the extension
            sub_extension = extension.get('extension', [])
            for sub_ext in sub_extension:
                value_codeable_concept = sub_ext.get('valueCodeableConcept', {})
                text = value_codeable_concept.get('text', '')

                # Check if 'text' is empty, if so, set it to the value of 'url'
                if not text:
                    value_codeable_concept['text'] = sub_ext['url']
                
                handle_extension_recursive(sub_ext)

# Add linkId to QuestionnaireResponse items
def add_link_id_to_questionnaire_response(resource):
    if resource['resourceType'] == 'QuestionnaireResponse' and 'item' in resource:
        for item_entry in resource['item']:
            # Check if 'linkId' is missing, and add it
            if 'linkId' not in item_entry:
                item_entry['linkId'] = generate_guid()  # You can use generate_guid() or any other logic to generate a unique linkId



# Function to send a single FHIR resource to the server
def send_resource(resource, json_file_path):
    #resource_id = resource.get('id') or generate_guid()
    resource_id = resource['id'] 
    endpoint_url = f"{base_url}/{resource['resourceType']}/{resource_id}"
    
    response = requests.put(endpoint_url, headers=headers, json=resource)

    if response.status_code not in [200, 201]:
        print(f"Error {response.status_code} for {resource['resourceType']} ({resource_id}): {response.text}")
        print(f"File path: {json_file_path}")
        print(f"resource: {resource}")

# Function to get individual resources from a FHIR bundle
def get_resources(bundle):
    resources = []

    prev_row_name = None

    for entry in bundle.get('entry', []):
        # Assuming each entry has a 'resource'
        resource = entry.get('resource')
        resource_id = resource.get('id') or generate_guid()
        resource['id'] = resource_id

        if resource:
        #if resource['resourceType'] == 'QuestionnaireResponse':
        
            # Handle 'description' property
            handle_description(resource, prev_row_name)


            # Handle 'title' property
            #handle_title(resource)
            # Function to handle text property
            #handle_text(resource)


            # Add linkId to QuestionnaireResponse items
            add_link_id_to_questionnaire_response(resource)
            # Check and move HealthcareService reference for Observation resources
            check_and_move_healthcare_service(resource)
            # Check and move HealthcareService reference for HealthcareService resources
            move_healthcare_service_reference(resource)
            # Handle MedicationRequest extension property
            handle_medication_request_extension(resource)
            # replace any emply with N/A
            replace_empty_with_na_fhir(resource)

            resources.append(resource)

            # Update prev_row_name for the next iteration
            prev_row_name = resource.get('name', None)

    return resources

# Function to sort resources based on dependencies (references)
def sort_resources(resources):
    sorted_resources = []
    processed_ids = set()

    def process_resource(resource):
        if resource['id'] not in processed_ids:
            for reference in resource.get('contained', []):
                process_resource(reference)

            sorted_resources.append(resource)
            processed_ids.add(resource['id'])

    for resource in resources:
        process_resource(resource)

    return sorted_resources


# Function to create a FHIR bundle from a list of resources
def create_bundle(resources):
    TransBundle = {
        'resourceType': 'Bundle',
        'type': 'transaction',  # Change type to 'transaction'
        'entry': [
            {
                'resource': resource,
                'request': {
                    'method': 'PUT',
                    'url': f"{resource['resourceType']}/{resource['id']}"
                }
            }
            for resource in resources
        ]
    }
    CollBundle = {
        'resourceType': 'Bundle',
        'type': 'collection',  # Change type to 'transaction'
        'entry': [
            {
                'resource': resource,
               
            }
            for resource in resources
        ]
    }
    return TransBundle, CollBundle

# Function to store a FHIR bundle as a JSON file
def store_bundle(bundle, filename):
    modified_bundle_path = os.path.join(modified_bundles_directory, filename)
    with open(modified_bundle_path, 'w', encoding='utf-8') as file:
        json.dump(bundle, file, ensure_ascii=False, indent=2)

# Function to send a FHIR bundle to the server
def send_bundle(TransBundle, CollBundle, json_file_path):
    # Send transaction bundle to create indivisual entries
    Trans_endpoint_url = f"{base_url}"
    Col_endpoint_url = Trans_endpoint_url + "Bundle"
    Transresponse = requests.post(Trans_endpoint_url, headers=headers, json=TransBundle)

    if Transresponse.status_code not in [200, 201]:
        print(f"Error {Transresponse.status_code} for Bundle: {Transresponse.text}")
        print(f"File path: {json_file_path}")
    else:
        store_bundle(TransBundle, filename)
        ColResponse = requests.post(Col_endpoint_url, headers=headers, json=CollBundle)

    
# Traverse the directory and process FHIR bundles
for foldername, subfolders, filenames in os.walk(root_directory):
    for filename in filenames:
        # Check if the file has a .json extension
        if filename.endswith('.json'):
            # Construct the full path to the FHIR bundle (JSON file)
            json_file_path = os.path.join(foldername, filename)

            # Read the FHIR bundle
            with open(json_file_path, encoding="utf8") as file:
                fhir_bundle = json.load(file)

            # Convert to a list of FHIR resources
            fhir_resources = get_resources(fhir_bundle)

            # Sort resources based on dependencies
            sorted_resources = sort_resources(fhir_resources)

            # Send each resource to the server
            #for resource in sorted_resources:
            #    send_resource(resource, json_file_path)

            TransBundle, CollBundle = create_bundle(sorted_resources)
            send_bundle(TransBundle, CollBundle , json_file_path)
