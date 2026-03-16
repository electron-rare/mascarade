# Gradio UI Verification Guide

## Prerequisites

1. Install the finetune extras (includes Gradio):
```bash
cd core
pip install -e ".[finetune]"
# or using the venv:
.venv/bin/pip install -e ".[finetune]"
```

## Starting the Server

1. Start the FastAPI server:
```bash
cd core
.venv/bin/python3 -m uvicorn mascarade.server:app --host 0.0.0.0 --port 8100 --reload
```

2. The server will automatically mount the Gradio UI at `/finetune` if Gradio is installed.

## Verification Steps

### 1. Access the UI

Open in browser: **http://localhost:8100/finetune**

### 2. Verify UI Renders

- [ ] Gradio interface loads without errors
- [ ] Four tabs are visible:
  - 📁 Dataset Upload
  - ⚙️ Training Configuration
  - 📊 Job Status
  - 📋 All Jobs

### 3. Verify Dataset Upload Form

In the "📁 Dataset Upload" tab:

- [ ] File upload widget is visible
- [ ] Dataset ID text field is present
- [ ] Domain text field is present
- [ ] Format dropdown shows: jsonl, parquet, csv
- [ ] "Upload Dataset" button is visible

**Test Upload:**
1. Create a test dataset file:
```bash
echo '{"messages": [{"role": "user", "content": "test"}]}' > test_dataset.jsonl
```
2. Upload the file through the UI
3. Fill in Dataset ID: `test-dataset-v1`
4. Fill in Domain: `test`
5. Click "Upload Dataset"
6. Verify success message appears

### 4. Verify Training Configuration Form

In the "⚙️ Training Configuration" tab:

- [ ] Base Model text field is present (default: unsloth/llama-3-8b)
- [ ] Training Method dropdown shows: lora, qlora, full, dpo
- [ ] Learning Rate slider is present
- [ ] Batch Size slider is present
- [ ] Epochs slider is present
- [ ] LoRA Parameters accordion is expandable
- [ ] "🚀 Launch Training" button is visible

**Test Training Submission:**
1. Ensure you've uploaded a dataset first
2. Keep default settings or adjust as needed
3. Click "🚀 Launch Training"
4. Verify success message with Job ID appears

### 5. Verify Job Status Display

In the "📊 Job Status" tab:

- [ ] Job ID field shows current job
- [ ] Status field shows job status
- [ ] Training Metrics JSON display is present
- [ ] "Refresh Status" button works

**Test Status Refresh:**
1. Submit a training job
2. Note the Job ID
3. Click "Refresh Status"
4. Verify status updates correctly

### 6. Verify All Jobs List

In the "📋 All Jobs" tab:

- [ ] Jobs dataframe displays with columns: Job ID, Base Model, Dataset, Method, Status, Started At
- [ ] "Refresh Jobs" button works
- [ ] Jobs list populates when jobs exist

**Test Jobs List:**
1. Click "Refresh Jobs"
2. Verify any submitted jobs appear in the table
3. Verify columns are populated correctly

## API Integration Verification

The Gradio UI integrates with these API endpoints:

1. **POST /api/finetune/jobs** - Submit new job
```bash
curl -X POST http://localhost:8100/api/finetune/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "/path/to/dataset.jsonl",
    "model": "unsloth/llama-3-8b",
    "method": "lora"
  }'
```

2. **GET /api/finetune/jobs** - List all jobs
```bash
curl http://localhost:8100/api/finetune/jobs
```

3. **GET /api/finetune/jobs/{job_id}** - Get job status
```bash
curl http://localhost:8100/api/finetune/jobs/{job_id}
```

## Success Criteria

All verification steps pass:
- ✅ Gradio UI renders at http://localhost:8100/finetune
- ✅ Upload form works (can upload dataset)
- ✅ Training form works (can submit job)
- ✅ Status display shows job information
- ✅ Jobs list displays all jobs
- ✅ No console errors in browser or server logs
