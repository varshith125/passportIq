import os
import sys
import json

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from app.pipeline.orchestrator import run_extraction_pipeline
from app.services.image_security import validate_and_decode_image
from app.services.preprocessing import preprocess_passport_image
from app.ocr.rapidocr_engine import get_ocr_manager

images = ['male_2.jpg', 'female_1.jpg', 'female_2.jpg', '1_QKnoCEqXCvRY1fQTJ5q0lQ.png']
ocr_mgr = get_ocr_manager()

eval_output = {}

for img_name in images:
    path = os.path.join(r'c:\Users\varsh\Downloads', img_name)
    if not os.path.exists(path):
        print(f"Skipping {img_name} (not found)")
        continue
    
    print('=' * 80)
    print(f"EVALUATING REAL IMAGE: {img_name}")
    print('=' * 80)
    
    with open(path, 'rb') as f:
        data = f.read()
        
    res = run_extraction_pipeline(data, filename=img_name)
    print(f"Status: {res.status.value}")
    print(f"Document Classification: {res.document_classification.value}")
    print(f"Active OCR Engine: {res.ocr_metadata.active_engine}")
    print(f"Detected Blocks: {res.ocr_metadata.detected_blocks_count}")
    print(f"Mean Confidence: {res.ocr_metadata.mean_ocr_confidence}")
    print(f"Processing Duration: {res.processing_duration_ms:.2f} ms")
    print(f"Preprocessing Resized: {res.preprocessing.resized_for_ocr} ({res.preprocessing.original_width}x{res.preprocessing.original_height} -> {res.preprocessing.processed_width}x{res.preprocessing.processed_height})")
    
    print("\n--- Extracted Fields ---")
    fields_dict = res.fields.model_dump()
    for fname, fval in fields_dict.items():
        v = fval.get('value')
        src = fval.get('source')
        st = fval.get('validation_state')
        notes = fval.get('notes')
        print(f"  {fname:<18}: {str(v):<28} [source={src}, validation={st}] {notes}")
        
    print("\n--- MRZ Extraction ---")
    print(f"  Detected: {res.mrz.detected}")
    print(f"  Format: {res.mrz.mrz_format}")
    print(f"  Check Digits Valid: {res.mrz.all_check_digits_valid}")
    if res.mrz.mrz_text:
        print("  MRZ Text:")
        for line in res.mrz.mrz_text.splitlines():
            print(f"    {line}")
    if res.mrz.errors:
        print(f"  MRZ Errors: {res.mrz.errors}")
        
    # Inspect raw OCR blocks
    decoded = validate_and_decode_image(data, img_name)
    prep = preprocess_passport_image(decoded)
    ocr_res = ocr_mgr.extract_text_blocks(prep.ocr_rgb)
    print(f"\n--- Raw OCR Blocks ({len(ocr_res.blocks)}) ---")
    blocks_data = []
    for i, b in enumerate(ocr_res.blocks):
        clean_text = b.text.encode('ascii', 'backslashreplace').decode('ascii')
        print(f"  [{i:02d}] conf={b.confidence:.2f} bbox=({b.min_x:6.1f}, {b.min_y:6.1f}, {b.max_x:6.1f}, {b.max_y:6.1f}) text={repr(clean_text)}")
        blocks_data.append({
            "index": i,
            "confidence": b.confidence,
            "bbox": [b.min_x, b.min_y, b.max_x, b.max_y],
            "text": b.text,
        })
    print("\n")

    eval_output[img_name] = {
        "status": res.status.value,
        "classification": res.document_classification.value,
        "active_engine": res.ocr_metadata.active_engine,
        "detected_blocks_count": res.ocr_metadata.detected_blocks_count,
        "mean_confidence": res.ocr_metadata.mean_ocr_confidence,
        "duration_ms": res.processing_duration_ms,
        "resized": res.preprocessing.resized_for_ocr,
        "fields": fields_dict,
        "mrz": {
            "detected": res.mrz.detected,
            "format": str(res.mrz.mrz_format),
            "all_check_digits_valid": res.mrz.all_check_digits_valid,
            "mrz_text": res.mrz.mrz_text,
            "errors": res.mrz.errors,
            "raw_lines": res.mrz.raw_lines,
        },
        "reconciliation": {
            "overall_status": res.reconciliation.overall_status.value,
            "matched_count": res.reconciliation.matched_count,
            "compared_fields_count": res.reconciliation.compared_fields_count,
            "mismatch_count": res.reconciliation.mismatch_count,
        },
        "ocr_blocks": blocks_data,
    }

with open(r'c:\Users\varsh\Downloads\passportiq-v2\backend\eval_results.json', 'w', encoding='utf-8') as f_out:
    json.dump(eval_output, f_out, indent=2, ensure_ascii=False)

print("Evaluation successfully written to eval_results.json")
