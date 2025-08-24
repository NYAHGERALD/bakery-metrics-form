# Bakery Metrics Dashboard - API Documentation

## Backend API Endpoints

### 1. Weekly Metrics Endpoint
**GET** `/api/weekly-metrics`

Returns OEE and waste performance data for charts.

**Query Parameters:**
- `week` (optional): Week identifier (default: 'latest')
- `date_range` (optional): 'current_week', 'last_week', 'last_30_days', 'last_quarter'
- `shift` (optional): 'all', 'first', 'second'
- `department` (optional): 'all', 'production', 'packaging', 'quality'
- `line` (optional): 'all', 'line_1', 'line_2'
- `area` (optional): Filter by specific area

**Example Request:**
```bash
curl "http://localhost:5002/api/weekly-metrics?week=latest&shift=first&department=production"
```

**Example Response:**
```json
{
  "week": "latest",
  "oee": [85.5, 82.3, 88.7, 76.2, 89.1],
  "waste": [2.1, 3.8, 2.5, 4.2, 1.9],
  "oeeAvg": 84.4,
  "wasteAvg": 2.9,
  "oeeFirstShift": [88.2, 85.1, 91.3, 79.5, 92.4],
  "wasteFirstShift": [1.8, 3.2, 2.1, 3.9, 1.5],
  "oeeSecondShift": [82.8, 79.5, 86.1, 72.9, 85.8],
  "wasteSecondShift": [2.4, 4.4, 2.9, 4.5, 2.3],
  "downtimeRatio": 5.2,
  "productionRate": 87.3
}
```

### 2. Dashboard KPIs Endpoint
**GET** `/api/dashboard-kpis`

Returns key performance indicators for dashboard cards.

**Query Parameters:**
- `date_range` (optional): Filter by time period
- `shift` (optional): Filter by shift
- `department` (optional): Filter by department

**Example Request:**
```bash
curl "http://localhost:5002/api/dashboard-kpis?date_range=current_week&shift=first"
```

**Example Response:**
```json
{
  "avgOEE": 84.4,
  "totalWaste": 23.7,
  "downtimeRatio": 5.2,
  "productionRate": 87.3,
  "availability": 94.8,
  "performance": 89.2,
  "quality": 97.1,
  "plannedDowntime": 2.1,
  "unplannedDowntime": 3.1,
  "totalProduction": 12543.8
}
```

## Form Submission Endpoint

### 3. Metrics Submission
**POST** `/submit`

Accepts form data for daily metrics submission.

**Form Fields:**
- `week`: Week identifier
- `day`: Day of week (Monday-Friday)  
- `submitted_by`: Name of submitter
- `oee_–_die_cut_1_(1st_shift)`: OEE percentage for Die Cut 1, First Shift
- `oee_–_die_cut_2_(1st_shift)`: OEE percentage for Die Cut 2, First Shift
- `pounds_–_die_cut_1_(1st_shift)`: Production pounds for Die Cut 1, First Shift
- `pounds_–_die_cut_2_(1st_shift)`: Production pounds for Die Cut 2, First Shift
- `waste_–_die_cut_1_(1st_shift)`: Waste percentage for Die Cut 1, First Shift
- `waste_–_die_cut_2_(1st_shift)`: Waste percentage for Die Cut 2, First Shift
- `oee_–_die_cut_1_(2nd_shift)`: OEE percentage for Die Cut 1, Second Shift
- `oee_–_die_cut_2_(2nd_shift)`: OEE percentage for Die Cut 2, Second Shift
- `pounds_–_die_cut_1_(2nd_shift)`: Production pounds for Die Cut 1, Second Shift
- `pounds_–_die_cut_2_(2nd_shift)`: Production pounds for Die Cut 2, Second Shift
- `waste_–_die_cut_1_(2nd_shift)`: Waste percentage for Die Cut 1, Second Shift
- `waste_–_die_cut_2_(2nd_shift)`: Waste percentage for Die Cut 2, Second Shift

**Example Request:**
```bash
curl -X POST http://localhost:5002/submit \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "week=Week of 2025-01-06&day=Monday&submitted_by=Test User&oee_–_die_cut_1_(1st_shift)=85.5&waste_–_die_cut_1_(1st_shift)=2.1"
```

## Filter Mapping

### Dashboard Filter Controls
- **Date Range**: Maps to `date_range` parameter
- **Shift**: Maps to `shift` parameter  
- **Department**: Maps to `department` parameter
- **Line**: Maps to `line` parameter

### Filter Values
- **Date Range**: 'current_week', 'last_week', 'last_30_days', 'last_quarter'
- **Shift**: 'all', 'first', 'second'
- **Department**: 'all', 'production', 'packaging', 'quality'
- **Line**: 'all', 'line_1', 'line_2'

## OEE Calculations

### OEE Formula
**OEE = Availability × Performance × Quality**

Where:
- **Availability**: (Planned Production Time - Downtime) / Planned Production Time
- **Performance**: (Total Count × Ideal Cycle Time) / Operating Time  
- **Quality**: Good Count / Total Count

### Component Calculations (from database)
```sql
-- Availability
SELECT (planned_downtime + unplanned_downtime) / planned_production_time * 100 as availability

-- Performance  
SELECT actual_output / target_output * 100 as performance

-- Quality
SELECT good_count / (good_count + reject_count) * 100 as quality

-- Overall OEE
SELECT availability * performance * quality / 10000 as oee_percentage
```

## Testing Commands

### Manual API Testing
```bash
# Test weekly metrics
curl "http://localhost:5002/api/weekly-metrics?week=latest"

# Test KPIs with filters
curl "http://localhost:5002/api/dashboard-kpis?shift=first&department=production"

# Test form submission
curl -X POST http://localhost:5002/submit \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "week=Week of 2025-01-06&day=Monday&submitted_by=Test&oee_–_die_cut_1_(1st_shift)=85"
```

### Environment Variables Required
```bash
SECRET_KEY=your-secret-key-change-this-in-production
DB_HOST=localhost
DB_NAME=bakery_metrics
DB_USER=bakery_app  
DB_PASSWORD=your_secure_app_password
DB_PORT=5432
```

## Error Handling

### Response Format
- **Success**: HTTP 200 with JSON data
- **Not Found**: HTTP 404 for invalid endpoints
- **Bad Request**: HTTP 400 for invalid parameters
- **Server Error**: HTTP 500 with error details

### Loading States
- Dashboard shows loading overlay during data fetch
- Filter button shows "Loading..." when applying filters
- Form shows progress bar during submission

### No Data Handling
- Charts display empty state when no data available
- KPI cards show "--" for missing values
- Graceful degradation to default/placeholder values