import csv
import io
import pandas as pd
import numpy as np
from datetime import datetime

def convert_to_24hr_format(time_str, default_ampm='AM'):
    """
    Convert 12-hour format time to 24-hour format.
    Handles various input formats including with/without AM/PM.
    """
    if not time_str or pd.isna(time_str):
        return None
        
    time_str = str(time_str).strip().upper()
    
    # Check if AM/PM is specified
    if 'AM' in time_str or 'PM' in time_str:
        # Extract AM/PM
        ampm = 'AM' if 'AM' in time_str else 'PM'
        # Remove AM/PM from the string
        time_str = time_str.replace('AM', '').replace('PM', '').strip()
    else:
        ampm = default_ampm
    
    # Parse the time
    if ':' in time_str:
        hour, minute = map(int, time_str.split(':'))
    else:
        # Handle numeric format (e.g., 830 for 8:30)
        if len(time_str) <= 2:
            hour = int(time_str)
            minute = 0
        else:
            time_str = time_str.zfill(4)  # Pad with zeros if needed
            hour = int(time_str[:-2])
            minute = int(time_str[-2:])
    
    # Adjust for PM (except for 12 PM which is already correct)
    if ampm == 'PM' and hour < 12:
        hour += 12
    # Adjust for 12 AM which should be 00
    elif ampm == 'AM' and hour == 12:
        hour = 0
        
    return f"{hour:02d}:{minute:02d}"

def process_csv_data(file):
    """
    Process CSV file with location data.
    
    Expected CSV format:
    name,address,time_window_start,time_window_end
    
    Args:
        file: Flask file object
        
    Returns:
        list: List of dictionaries containing location data
    """
    # Read CSV file
    content = file.read().decode('utf-8')
    
    # Reset file pointer for potential future use
    file.seek(0)
    
    # Parse CSV
    locations = []
    
    try:
        # First try using pandas which handles various CSV formats better
        df = pd.read_csv(io.StringIO(content))
        
        # Normalize column names (lowercase, remove spaces)
        df.columns = [col.lower().replace(' ', '_') for col in df.columns]
        
        required_columns = ['name', 'address']
        optional_columns = ['time_window_start', 'time_window_end', 'latitude', 'longitude']
        
        # Check if required columns exist
        for col in required_columns:
            if col not in df.columns:
                raise ValueError(f"Required column '{col}' not found in CSV")
        
        # Process each row
        for _, row in df.iterrows():
            location = {
                'name': row['name'],
                'address': row['address']
            }
            
            # Add optional columns if they exist
            for col in optional_columns:
                if col in df.columns and not pd.isna(row[col]):
                    location[col] = row[col]
            
            # Parse time windows if present
            if 'time_window_start' in location and location['time_window_start']:
                try:
                    # Convert to 24-hour format
                    time_str = convert_to_24hr_format(location['time_window_start'], 'AM')
                    if time_str:
                        location['time_window_start'] = datetime.strptime(time_str, '%H:%M').time()
                    else:
                        location['time_window_start'] = None
                except ValueError:
                    # Skip invalid time
                    location['time_window_start'] = None
            
            if 'time_window_end' in location and location['time_window_end']:
                try:
                    # Convert to 24-hour format
                    time_str = convert_to_24hr_format(location['time_window_end'], 'PM')
                    if time_str:
                        location['time_window_end'] = datetime.strptime(time_str, '%H:%M').time()
                    else:
                        location['time_window_end'] = None
                except ValueError:
                    # Skip invalid time
                    location['time_window_end'] = None
            
            locations.append(location)
    
    except Exception as e:
        # Fallback to simple CSV parsing
        try:
            reader = csv.DictReader(io.StringIO(content))
            
            for row in reader:
                # Clean up keys (lowercase, remove spaces)
                clean_row = {k.lower().replace(' ', '_'): v for k, v in row.items()}
                
                # Check required fields
                if 'name' not in clean_row or 'address' not in clean_row:
                    continue
                
                location = {
                    'name': clean_row['name'],
                    'address': clean_row['address']
                }
                
                # Add time windows if present
                if 'time_window_start' in clean_row and clean_row['time_window_start']:
                    try:
                        time_str = convert_to_24hr_format(clean_row['time_window_start'], 'AM')
                        if time_str:
                            location['time_window_start'] = datetime.strptime(time_str, '%H:%M').time()
                    except ValueError:
                        pass
                
                if 'time_window_end' in clean_row and clean_row['time_window_end']:
                    try:
                        time_str = convert_to_24hr_format(clean_row['time_window_end'], 'PM')
                        if time_str:
                            location['time_window_end'] = datetime.strptime(time_str, '%H:%M').time()
                    except ValueError:
                        pass
                
                locations.append(location)
        
        except Exception as inner_e:
            # If both methods fail, return empty list
            print(f"Error processing CSV: {e}, {inner_e}")
            return []
    
    return locations

def prepare_sample_data():
    """
    Create sample data for testing.
    
    Returns:
        list: List of dictionaries containing sample location data
    """
    # Sample data with common city addresses
    sample_data = [
        {
            'name': 'Warehouse',
            'address': '123 Main St, New York, NY',
            'time_window_start': datetime.strptime('08:00', '%H:%M').time(),
            'time_window_end': datetime.strptime('18:00', '%H:%M').time(),
        },
        {
            'name': 'Customer A',
            'address': '456 Park Ave, New York, NY',
            'time_window_start': datetime.strptime('09:00', '%H:%M').time(),
            'time_window_end': datetime.strptime('12:00', '%H:%M').time(),
        },
        {
            'name': 'Customer B',
            'address': '789 Broadway, New York, NY',
            'time_window_start': datetime.strptime('10:00', '%H:%M').time(),
            'time_window_end': datetime.strptime('14:00', '%H:%M').time(),
        },
        {
            'name': 'Customer C',
            'address': '101 5th Ave, New York, NY',
            'time_window_start': datetime.strptime('13:00', '%H:%M').time(),
            'time_window_end': datetime.strptime('16:00', '%H:%M').time(),
        },
        {
            'name': 'Customer D',
            'address': '202 E 42nd St, New York, NY',
            'time_window_start': datetime.strptime('09:30', '%H:%M').time(),
            'time_window_end': datetime.strptime('17:00', '%H:%M').time(),
        }
    ]
    
    return sample_data

def export_to_csv(locations, filename="locations.csv"):
    """
    Export locations to a CSV file.
    
    Args:
        locations (list): List of location dictionaries
        filename (str): Name of the output file
        
    Returns:
        str: Path to the created CSV file
    """
    # Prepare data for CSV
    data = []
    for loc in locations:
        row = {
            'name': loc['name'],
            'address': loc['address']
        }
        
        # Add time windows if present
        if 'time_window_start' in loc and loc['time_window_start']:
            if isinstance(loc['time_window_start'], datetime.time):
                hour = loc['time_window_start'].hour
                minute = loc['time_window_start'].minute
                # Convert to 12-hour format with AM/PM
                ampm = 'AM'
                if hour >= 12:
                    ampm = 'PM'
                    if hour > 12:
                        hour -= 12
                if hour == 0:
                    hour = 12
                row['time_window_start'] = f"{hour}:{minute:02d} {ampm}"
            else:
                row['time_window_start'] = loc['time_window_start']
        
        if 'time_window_end' in loc and loc['time_window_end']:
            if isinstance(loc['time_window_end'], datetime.time):
                hour = loc['time_window_end'].hour
                minute = loc['time_window_end'].minute
                # Convert to 12-hour format with AM/PM
                ampm = 'AM'
                if hour >= 12:
                    ampm = 'PM'
                    if hour > 12:
                        hour -= 12
                if hour == 0:
                    hour = 12
                row['time_window_end'] = f"{hour}:{minute:02d} {ampm}"
            else:
                row['time_window_end'] = loc['time_window_end']
        
        # Add coordinates if present
        if 'latitude' in loc and 'longitude' in loc:
            row['latitude'] = loc['latitude']
            row['longitude'] = loc['longitude']
        
        data.append(row)
    
    # Create DataFrame and save to CSV
    df = pd.DataFrame(data)
    df.to_csv(filename, index=False)
    
    return filename

def generate_random_locations(center_lat, center_lng, count=10, radius=10):
    """
    Generate random delivery locations around a center point.
    
    Args:
        center_lat (float): Center latitude
        center_lng (float): Center longitude
        count (int): Number of locations to generate
        radius (float): Maximum radius in kilometers
        
    Returns:
        list: List of dictionaries containing random location data
    """
    locations = []
    
    # Generate random points within radius
    for i in range(count):
        # Random distance within radius (in km)
        distance = radius * np.sqrt(np.random.random())
        
        # Random angle
        angle = np.random.random() * 2 * np.pi
        
        # Convert to latitude/longitude
        # Approximate conversion: 1 degree latitude ≈ 111 km, 1 degree longitude varies with latitude
        lat_offset = distance / 111.0 * np.cos(angle)
        lng_offset = distance / (111.0 * np.cos(np.radians(center_lat))) * np.sin(angle)
        
        lat = center_lat + lat_offset
        lng = center_lng + lng_offset
        
        # Random time windows (between 8 AM and 6 PM)
        start_hour = np.random.randint(8, 16)
        start_minute = np.random.choice([0, 15, 30, 45])
        
        # End time 1-3 hours after start
        duration = np.random.randint(1, 4)
        end_hour = min(start_hour + duration, 18)
        end_minute = start_minute
        
        # Convert to AM/PM format for display
        start_ampm = "AM" if start_hour < 12 else "PM"
        end_ampm = "AM" if end_hour < 12 else "PM"
        
        display_start_hour = start_hour if start_hour <= 12 else start_hour - 12
        display_end_hour = end_hour if end_hour <= 12 else end_hour - 12
        
        # Ensure 12-hour format is correct (0 hour is 12 AM)
        if display_start_hour == 0:
            display_start_hour = 12
        if display_end_hour == 0:
            display_end_hour = 12
        
        # Create location
        location = {
            'name': f'Random Location {i+1}',
            'address': f'Random Address {i+1}',
            'latitude': lat,
            'longitude': lng,
            'time_window_start': datetime.strptime(f'{start_hour:02d}:{start_minute:02d}', '%H:%M').time(),
            'time_window_end': datetime.strptime(f'{end_hour:02d}:{end_minute:02d}', '%H:%M').time(),
            'display_time_window': f'{display_start_hour}:{start_minute:02d} {start_ampm} - {display_end_hour}:{end_minute:02d} {end_ampm}'
        }
        
        locations.append(location)
    
    return locations