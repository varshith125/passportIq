import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { formatExtractionForClipboard } from '../features/scanner/formatClipboardText';
import { validateClientFile } from '../features/scanner/usePassportScanner';
import type { PassportExtractionResponse } from '../types/passport';

const mockSampleResponse: PassportExtractionResponse = {
  status: 'completed',
  document_classification: 'passport_td3',
  fields: {
    document_type: {
      field_name: 'document_type',
      label: 'Document Type',
      value: 'P',
      raw_evidence: 'MRZ:P | VIZ:Type -> P',
      source: 'reconciled',
      validation_state: 'valid_format',
      ocr_confidence: 0.99,
      reconciliation_status: 'matched',
      mrz_value: 'P',
      viz_value: 'P',
      notes: [],
    },
    issuing_country: {
      field_name: 'issuing_country',
      label: 'Issuing Country / Authority',
      value: 'UTO',
      raw_evidence: 'MRZ:UTO | VIZ:Issuing Country -> UTO',
      source: 'reconciled',
      validation_state: 'valid_format',
      ocr_confidence: 0.99,
      reconciliation_status: 'matched',
      mrz_value: 'UTO',
      viz_value: 'UTO',
      notes: [],
    },
    surname: {
      field_name: 'surname',
      label: 'Surname',
      value: 'ERIKSSON',
      raw_evidence: 'MRZ:ERIKSSON | VIZ:Surname -> ERIKSSON',
      source: 'reconciled',
      validation_state: 'valid_format',
      ocr_confidence: 0.99,
      reconciliation_status: 'matched',
      mrz_value: 'ERIKSSON',
      viz_value: 'ERIKSSON',
      notes: [],
    },
    given_names: {
      field_name: 'given_names',
      label: 'Given Names',
      value: 'ANNA MARIA',
      raw_evidence: 'MRZ:ANNA MARIA | VIZ:Given Names -> ANNA MARIA',
      source: 'reconciled',
      validation_state: 'valid_format',
      ocr_confidence: 0.99,
      reconciliation_status: 'matched',
      mrz_value: 'ANNA MARIA',
      viz_value: 'ANNA MARIA',
      notes: [],
    },
    full_name: {
      field_name: 'full_name',
      label: 'Full Name',
      value: 'ANNA MARIA ERIKSSON',
      raw_evidence: 'MRZ:ANNA MARIA ERIKSSON',
      source: 'reconciled',
      validation_state: 'valid_format',
      ocr_confidence: 0.99,
      reconciliation_status: 'matched',
      mrz_value: 'ANNA MARIA ERIKSSON',
      viz_value: 'ANNA MARIA ERIKSSON',
      notes: [],
    },
    passport_number: {
      field_name: 'passport_number',
      label: 'Passport Number',
      value: 'L898902C3',
      raw_evidence: 'MRZ:L898902C3',
      source: 'reconciled',
      validation_state: 'valid_check_digit',
      ocr_confidence: 0.99,
      reconciliation_status: 'matched',
      mrz_value: 'L898902C3',
      viz_value: 'L898902C3',
      notes: [],
    },
    nationality: {
      field_name: 'nationality',
      label: 'Nationality',
      value: 'UTO',
      raw_evidence: 'MRZ:UTO',
      source: 'reconciled',
      validation_state: 'valid_format',
      ocr_confidence: 0.98,
      reconciliation_status: 'matched',
      mrz_value: 'UTO',
      viz_value: 'UTOPIA',
      notes: [],
    },
    date_of_birth: {
      field_name: 'date_of_birth',
      label: 'Date of Birth',
      value: '1974-08-12',
      raw_evidence: 'MRZ:1974-08-12',
      source: 'reconciled',
      validation_state: 'valid_check_digit',
      ocr_confidence: 0.98,
      reconciliation_status: 'matched',
      mrz_value: '1974-08-12',
      viz_value: '1974-08-12',
      notes: [],
    },
    sex: {
      field_name: 'sex',
      label: 'Sex',
      value: 'F',
      raw_evidence: 'MRZ:F',
      source: 'reconciled',
      validation_state: 'valid_format',
      ocr_confidence: 0.99,
      reconciliation_status: 'matched',
      mrz_value: 'F',
      viz_value: 'F',
      notes: [],
    },
    date_of_expiry: {
      field_name: 'date_of_expiry',
      label: 'Date of Expiry',
      value: '2030-04-15',
      raw_evidence: 'MRZ:2030-04-15',
      source: 'reconciled',
      validation_state: 'valid_check_digit',
      ocr_confidence: 0.98,
      reconciliation_status: 'matched',
      mrz_value: '2030-04-15',
      viz_value: '2030-04-15',
      notes: [],
    },
    date_of_issue: {
      field_name: 'date_of_issue',
      label: 'Date of Issue',
      value: '2020-04-15',
      raw_evidence: 'VIZ:15 APR 2020',
      source: 'viz',
      validation_state: 'valid_format',
      ocr_confidence: 0.97,
      reconciliation_status: 'not_checked',
      mrz_value: null,
      viz_value: '2020-04-15',
      notes: [],
    },
    place_of_birth: {
      field_name: 'place_of_birth',
      label: 'Place of Birth',
      value: null,
      raw_evidence: null,
      source: 'unavailable',
      validation_state: 'missing',
      ocr_confidence: null,
      reconciliation_status: 'not_checked',
      mrz_value: null,
      viz_value: null,
      notes: [],
    },
    personal_number: {
      field_name: 'personal_number',
      label: 'Personal / Optional Number',
      value: 'ZE184226B',
      raw_evidence: 'MRZ:ZE184226B',
      source: 'mrz',
      validation_state: 'valid_check_digit',
      ocr_confidence: 0.99,
      reconciliation_status: 'insufficient_data',
      mrz_value: 'ZE184226B',
      viz_value: null,
      notes: [],
    },
  },
  mrz: {
    detected: true,
    mrz_format: 'TD3',
    raw_lines: [
      'P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<',
      'L898902C36UTO7408122F3004157ZE184226B<<<<<16',
    ],
    normalized_lines: [
      'P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<',
      'L898902C36UTO7408122F3004157ZE184226B<<<<<16',
    ],
    mrz_text:
      'P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\nL898902C36UTO7408122F3004157ZE184226B<<<<<16',
    check_digits: [
      {
        field_name: 'passport_number',
        data_segment: 'L898902C3',
        expected_digit: '6',
        actual_digit: '6',
        is_valid: true,
        position_description: 'TD3 Line 2 [1-9] check digit at [10]',
      },
    ],
    all_check_digits_valid: true,
    line_length_valid: true,
    character_set_valid: true,
    recovery_applied: false,
    recovery_notes: [],
    errors: [],
    parsed_fields: {
      passport_number: 'L898902C3',
      surname: 'ERIKSSON',
    },
    ocr_confidence: 0.99,
    authenticity_disclaimer:
      'Valid MRZ check digits confirm only internal character consistency under ICAO 9303 and do not verify document authenticity or cryptographic signatures.',
  },
  reconciliation: {
    overall_status: 'matched',
    compared_fields_count: 9,
    matched_count: 9,
    mismatch_count: 0,
    insufficient_data_count: 2,
    not_checked_count: 2,
    items: [],
  },
  ocr_metadata: {
    requested_engine: 'rapidocr',
    active_engine: 'rapidocr_onnxruntime',
    fallback_used: false,
    fallback_reason: null,
    detected_blocks_count: 24,
    mean_ocr_confidence: 0.985,
    min_ocr_confidence: 0.96,
    max_ocr_confidence: 0.99,
    ocr_confidence_note:
      'OCR engine confidence reflects character recognition certainty from the model and is separate from semantic field-extraction accuracy or document validity.',
  },
  preprocessing: {
    original_width: 900,
    original_height: 600,
    original_format: 'PNG',
    original_mode: 'RGB',
    file_size_bytes: 42000,
    exif_orientation_applied: false,
    exif_orientation_tag: null,
    resized_for_ocr: false,
    processed_width: 900,
    processed_height: 600,
    steps_applied: ['grayscale_conversion'],
    grayscale_applied: true,
    contrast_adjusted: false,
    denoised: false,
    deskew_angle_degrees: 0.0,
    threshold_applied: false,
  },
  warnings: [
    {
      code: 'RECONCILIATION_INSUFFICIENT_DATA',
      severity: 'info',
      message: 'Personal number was present in MRZ only.',
      field_name: 'personal_number',
    },
  ],
  processing_duration_ms: 28.4,
  transient_processing_notice:
    'Uploaded image bytes were processed transiently in memory and were not persisted to disk or database.',
};

describe('PassPortIQ Frontend Suite', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('validates client-side file constraints accurately', () => {
    const emptyFile = new File([], 'empty.png', { type: 'image/png' });
    expect(validateClientFile(emptyFile)?.code).toBe('EMPTY_FILE');

    // Any non-empty file format (e.g. PDF, images) is now accepted
    const pdfFile = new File(['%PDF-1.5 test'], 'passport.pdf', {
      type: 'application/pdf',
    });
    expect(validateClientFile(pdfFile)).toBeNull();

    const validFile = new File(['valid_bytes'], 'passport.png', {
      type: 'image/png',
    });
    expect(validateClientFile(validFile)).toBeNull();
  });

  it('formats extracted fields and MRZ text for clipboard copy', () => {
    const formatted = formatExtractionForClipboard(mockSampleResponse);
    expect(formatted).toContain('PassPortIQ — Extracted Passport Summary');
    expect(formatted).toContain('Passport Number: L898902C3');
    expect(formatted).toContain('Surname: ERIKSSON');
    expect(formatted).toContain('P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<');
  });

  it('renders upload interface, processes image, displays results, and resets cleanly', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockSampleResponse,
    } as Response);

    render(<App />);

    expect(
      screen.getByText('Upload a Passport Image or Document'),
    ).toBeInTheDocument();

    const fileInput = screen.getByLabelText('Passport image file input');
    const sampleFile = new File(['fake_png_bytes'], 'eriksson.png', {
      type: 'image/png',
    });

    fireEvent.change(fileInput, { target: { files: [sampleFile] } });

    await waitFor(() => {
      expect(screen.getByText('Extraction Overview')).toBeInTheDocument();
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(screen.getAllByText('L898902C3')[0]).toBeInTheDocument();
    expect(screen.getAllByText('ERIKSSON')[0]).toBeInTheDocument();
    expect(screen.getByText('ANNA MARIA ERIKSSON')).toBeInTheDocument();
    expect(
      screen.getByText(
        'P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<',
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/RECONCILIATION_INSUFFICIENT_DATA/),
    ).toBeInTheDocument();

    // Reset back to upload screen
    await act(async () => {
      fireEvent.click(screen.getByText('Scan Another Document'));
    });
    await waitFor(() => {
      expect(
        screen.getByText('Upload a Passport Image or Document'),
      ).toBeInTheDocument();
    });
  });

  it('displays structured error banner when backend returns an error', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: false,
      status: 415,
      json: async () => ({
        error: {
          code: 'INVALID_FILE_SIGNATURE',
          message: 'Unsupported or unrecognized file signature.',
        },
      }),
    } as Response);

    render(<App />);
    const fileInput = screen.getByLabelText('Passport image file input');
    const badFile = new File(['spoofed'], 'spoofed.png', { type: 'image/png' });

    fireEvent.change(fileInput, { target: { files: [badFile] } });

    await waitFor(() => {
      expect(
        screen.getByText(/Extraction Failed \(INVALID_FILE_SIGNATURE\)/),
      ).toBeInTheDocument();
    });
  });
});
