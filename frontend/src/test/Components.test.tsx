import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ExtractionDetails } from '../components/ExtractionDetails';
import { FieldTable } from '../components/FieldTable';
import { PassportPreview } from '../components/PassportPreview';
import { formatDisplayFieldValue } from '../features/scanner/formatFieldValue';
import type { PassportExtractionResponse } from '../types/passport';

const mockResponse: PassportExtractionResponse = {
  status: 'completed',
  document_classification: 'passport_td3',
  fields: {
    document_type: {
      field_name: 'document_type',
      label: 'Document Type',
      value: 'P',
      raw_evidence: 'MRZ:P',
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
      value: 'USA',
      raw_evidence: 'USA',
      source: 'reconciled',
      validation_state: 'valid_format',
      ocr_confidence: 0.99,
      reconciliation_status: 'matched',
      mrz_value: 'USA',
      viz_value: 'USA',
      notes: [],
    },
    surname: {
      field_name: 'surname',
      label: 'Surname',
      value: 'FLORES',
      raw_evidence: 'FLORES',
      source: 'reconciled',
      validation_state: 'valid_format',
      ocr_confidence: 0.98,
      reconciliation_status: 'matched',
      mrz_value: 'FLORES',
      viz_value: 'FLORES',
      notes: [],
    },
    given_names: {
      field_name: 'given_names',
      label: 'Given Names',
      value: 'KATHERINE',
      raw_evidence: 'KATHERINE',
      source: 'reconciled',
      validation_state: 'valid_format',
      ocr_confidence: 0.98,
      reconciliation_status: 'matched',
      mrz_value: 'KATHERINE',
      viz_value: 'KATHERINE',
      notes: [],
    },
    full_name: {
      field_name: 'full_name',
      label: 'Full Name',
      value: 'KATHERINE FLORES',
      raw_evidence: 'KATHERINE FLORES',
      source: 'reconciled',
      validation_state: 'valid_format',
      ocr_confidence: 0.98,
      reconciliation_status: 'matched',
      mrz_value: 'KATHERINE FLORES',
      viz_value: 'KATHERINE FLORES',
      notes: [],
    },
    passport_number: {
      field_name: 'passport_number',
      label: 'Passport Number',
      value: '990280124',
      raw_evidence: '990280124',
      source: 'reconciled',
      validation_state: 'valid_check_digit',
      ocr_confidence: 0.99,
      reconciliation_status: 'matched',
      mrz_value: '990280124',
      viz_value: '990280124',
      notes: [],
    },
    nationality: {
      field_name: 'nationality',
      label: 'Nationality',
      value: 'USA',
      raw_evidence: 'USA',
      source: 'reconciled',
      validation_state: 'valid_format',
      ocr_confidence: 0.99,
      reconciliation_status: 'matched',
      mrz_value: 'USA',
      viz_value: 'UNITED STATES OF AMERICA',
      notes: [],
    },
    date_of_birth: {
      field_name: 'date_of_birth',
      label: 'Date of Birth',
      value: '1988-10-14',
      raw_evidence: '14 OCT 1988',
      source: 'reconciled',
      validation_state: 'valid_check_digit',
      ocr_confidence: 0.98,
      reconciliation_status: 'matched',
      mrz_value: '1988-10-14',
      viz_value: '1988-10-14',
      notes: [],
    },
    sex: {
      field_name: 'sex',
      label: 'Sex',
      value: 'F',
      raw_evidence: 'F',
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
      value: '2030-05-18',
      raw_evidence: '18 MAY 2030',
      source: 'reconciled',
      validation_state: 'valid_check_digit',
      ocr_confidence: 0.98,
      reconciliation_status: 'matched',
      mrz_value: '2030-05-18',
      viz_value: '2030-05-18',
      notes: [],
    },
    date_of_issue: {
      field_name: 'date_of_issue',
      label: 'Date of Issue',
      value: '2020-05-19',
      raw_evidence: '19 MAY 2020',
      source: 'viz',
      validation_state: 'valid_format',
      ocr_confidence: 0.97,
      reconciliation_status: 'not_checked',
      mrz_value: null,
      viz_value: '2020-05-19',
      notes: [],
    },
    place_of_birth: {
      field_name: 'place_of_birth',
      label: 'Place of Birth',
      value: 'FLORIDA, U.S.A.',
      raw_evidence: 'FLORIDA, U.S.A.',
      source: 'viz',
      validation_state: 'valid_format',
      ocr_confidence: 0.97,
      reconciliation_status: 'not_checked',
      mrz_value: null,
      viz_value: 'FLORIDA, U.S.A.',
      notes: [],
    },
    personal_number: {
      field_name: 'personal_number',
      label: 'Personal / Optional Number',
      value: null,
      raw_evidence: null,
      source: 'unavailable',
      validation_state: 'missing',
      ocr_confidence: null,
      reconciliation_status: 'insufficient_data',
      mrz_value: null,
      viz_value: null,
      notes: [],
    },
  },
  mrz: {
    detected: true,
    mrz_format: 'TD3',
    raw_lines: [
      'P<USAFLORES<<KATHERINE<<<<<<<<<<<<<<<<<<<<<<',
      '9902801243USA8810145F3005182<<<<<<<<<<<<<<00',
    ],
    normalized_lines: [
      'P<USAFLORES<<KATHERINE<<<<<<<<<<<<<<<<<<<<<<',
      '9902801243USA8810145F3005182<<<<<<<<<<<<<<00',
    ],
    mrz_text:
      'P<USAFLORES<<KATHERINE<<<<<<<<<<<<<<<<<<<<<<\n9902801243USA8810145F3005182<<<<<<<<<<<<<<00',
    check_digits: [
      {
        field_name: 'passport_number',
        data_segment: '990280124',
        expected_digit: '3',
        actual_digit: '3',
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
      passport_number: '990280124',
      surname: 'FLORES',
      given_names: 'KATHERINE',
    },
    ocr_confidence: 0.985,
    authenticity_disclaimer:
      'Valid MRZ check digits confirm only internal character consistency under ICAO 9303 and do not verify document authenticity.',
  },
  reconciliation: {
    overall_status: 'matched',
    compared_fields_count: 8,
    matched_count: 8,
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
    detected_blocks_count: 18,
    mean_ocr_confidence: 0.985,
    min_ocr_confidence: 0.96,
    max_ocr_confidence: 0.99,
    ocr_confidence_note:
      'OCR engine confidence reflects character recognition certainty.',
  },
  preprocessing: {
    original_width: 1200,
    original_height: 800,
    original_format: 'PNG',
    original_mode: 'RGB',
    file_size_bytes: 54000,
    exif_orientation_applied: false,
    exif_orientation_tag: null,
    resized_for_ocr: false,
    processed_width: 1200,
    processed_height: 800,
    steps_applied: ['grayscale_conversion'],
    grayscale_applied: true,
    contrast_adjusted: false,
    denoised: false,
    deskew_angle_degrees: 0.0,
    threshold_applied: false,
  },
  warnings: [],
  processing_duration_ms: 32.5,
  transient_processing_notice:
    'Uploaded image bytes were processed transiently in memory.',
};

describe('PassportPreview Component', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders preview toolbar, zoom controls, and filter pills', () => {
    const mockFile = new File(['mock_image'], 'test-passport.jpg', {
      type: 'image/jpeg',
    });
    const onReplaceMock = vi.fn();

    render(
      <PassportPreview
        file={mockFile}
        phase="completed"
        preprocessing={mockResponse.preprocessing}
        onReplaceFile={onReplaceMock}
      />,
    );

    expect(screen.getByText('test-passport.jpg')).toBeInTheDocument();
    expect(screen.getByText('100%')).toBeInTheDocument();

    // Zoom In
    const zoomInBtn = screen.getByLabelText('Zoom in preview');
    fireEvent.click(zoomInBtn);
    expect(screen.getByText('125%')).toBeInTheDocument();

    // Reset Zoom
    const resetZoomBtn = screen.getByLabelText('Reset zoom and position');
    fireEvent.click(resetZoomBtn);
    expect(screen.getByText('100%')).toBeInTheDocument();

    // Inspect filter modes
    const contrastBtn = screen.getByRole('radio', { name: /Contrast/i });
    fireEvent.click(contrastBtn);
    expect(contrastBtn).toHaveClass('pill-btn--active');

    const bwBtn = screen.getByRole('radio', { name: /B&W/i });
    fireEvent.click(bwBtn);
    expect(bwBtn).toHaveClass('pill-btn--active');
  });

  it('allows replacing image via file input', () => {
    const mockFile = new File(['mock_image'], 'old.png', { type: 'image/png' });
    const onReplaceMock = vi.fn();

    render(
      <PassportPreview
        file={mockFile}
        phase="completed"
        onReplaceFile={onReplaceMock}
      />,
    );

    const replaceInput = screen.getByLabelText('Replace passport document input');
    const newFile = new File(['new_image'], 'new.png', { type: 'image/png' });
    fireEvent.change(replaceInput, { target: { files: [newFile] } });

    expect(onReplaceMock).toHaveBeenCalledWith(newFile);
  });
});

describe('ExtractionDetails Component', () => {
  it('renders all personal and passport fields correctly including Place of Birth', () => {
    const onResetMock = vi.fn();
    render(<ExtractionDetails data={mockResponse} onReset={onResetMock} />);

    // Personal info
    expect(screen.getAllByText('FLORES')[0]).toBeInTheDocument();
    expect(screen.getAllByText('KATHERINE')[0]).toBeInTheDocument();
    expect(screen.getByText('KATHERINE FLORES')).toBeInTheDocument();
    expect(screen.getByText('FLORIDA, U.S.A.')).toBeInTheDocument();

    // Passport info
    expect(screen.getAllByText('990280124')[0]).toBeInTheDocument();
    expect(screen.getByText('2030-05-18')).toBeInTheDocument();
    expect(screen.getByText('2020-05-19')).toBeInTheDocument();

    // MRZ code lines
    expect(
      screen.getByText('P<USAFLORES<<KATHERINE<<<<<<<<<<<<<<<<<<<<<<'),
    ).toBeInTheDocument();
  });

  it('copies individual field to clipboard on click', async () => {
    const clipboardSpy = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: clipboardSpy,
      },
    });

    render(<ExtractionDetails data={mockResponse} onReset={vi.fn()} />);

    const copyPobBtn = screen.getByLabelText('Copy Place of Birth');
    fireEvent.click(copyPobBtn);

    await waitFor(() => {
      expect(clipboardSpy).toHaveBeenCalledWith('FLORIDA, U.S.A.');
    });
  });

  it('toggles technical diagnostics accordion open and closed', () => {
    render(<ExtractionDetails data={mockResponse} onReset={vi.fn()} />);

    const toggleBtn = screen.getByText(
      /Technical Diagnostics, Preprocessing & Privacy Metadata/i,
    );
    expect(screen.queryByText('OCR Engine Execution')).not.toBeInTheDocument();

    fireEvent.click(toggleBtn);
    expect(screen.getByText('OCR Engine Execution')).toBeInTheDocument();
    expect(screen.getAllByText('rapidocr_onnxruntime')[0]).toBeInTheDocument();

    fireEvent.click(toggleBtn);
    expect(screen.queryByText('OCR Engine Execution')).not.toBeInTheDocument();
  });

  it('formats sex codes human-readably in UI and preserves < and X as unspecified', () => {
    expect(formatDisplayFieldValue('sex', 'M')).toBe('Male (M)');
    expect(formatDisplayFieldValue('sex', 'MALE')).toBe('Male (M)');
    expect(formatDisplayFieldValue('sex', 'MASCULIN')).toBe('Male (M)');
    expect(formatDisplayFieldValue('sex', 'F')).toBe('Female (F)');
    expect(formatDisplayFieldValue('sex', 'FEMALE')).toBe('Female (F)');
    expect(formatDisplayFieldValue('sex', 'FÉMININ')).toBe('Female (F)');
    expect(formatDisplayFieldValue('sex', 'X')).toBe('X (Unspecified)');
    expect(formatDisplayFieldValue('sex', 'UNSPECIFIED')).toBe('X (Unspecified)');
    expect(formatDisplayFieldValue('sex', '<')).toBe('< (Unspecified)');
    expect(formatDisplayFieldValue('surname', 'LOPEZ')).toBe('LOPEZ');
  });

  it('renders FieldTable with formatted display values and diagnostic subnotes', () => {
    render(<FieldTable fields={mockResponse.fields} />);

    // Table headers
    expect(screen.getByText('Extracted Passport Fields')).toBeInTheDocument();
    expect(screen.getByText('MRZ vs. VIZ Reconciliation')).toBeInTheDocument();

    // Check formatted values
    expect(screen.getByText('Female (F)')).toBeInTheDocument();
    expect(screen.getByText('FLORIDA, U.S.A.')).toBeInTheDocument();
  });

  it('toggles view mode between Grouped Cards and Detailed Matrix', () => {
    render(<ExtractionDetails data={mockResponse} onReset={vi.fn()} />);

    // Initially in grouped cards view
    expect(screen.getByText('Personal Information')).toBeInTheDocument();
    expect(screen.queryByText('Extracted Passport Fields')).not.toBeInTheDocument();

    // Switch to Detailed Matrix view
    const matrixBtn = screen.getByRole('button', { name: /Detailed Matrix/i });
    fireEvent.click(matrixBtn);
    expect(screen.getByText('Extracted Passport Fields')).toBeInTheDocument();

    // Switch back to Grouped Cards view
    const cardsBtn = screen.getByRole('button', { name: /Grouped Cards/i });
    fireEvent.click(cardsBtn);
    expect(screen.getByText('Personal Information')).toBeInTheDocument();
    expect(screen.queryByText('Extracted Passport Fields')).not.toBeInTheDocument();
  });

  it('renders discrepancy callout banner when VIZ and MRZ conflict', () => {
    const conflictResponse: PassportExtractionResponse = {
      ...mockResponse,
      reconciliation: {
        ...mockResponse.reconciliation,
        overall_status: 'mismatch',
        mismatch_count: 1,
      },
      fields: {
        ...mockResponse.fields,
        surname: {
          ...mockResponse.fields.surname,
          reconciliation_status: 'mismatch',
          validation_state: 'conflict',
          value: 'FLORES',
          mrz_value: 'FLORES',
          viz_value: 'FLOREZ',
          raw_evidence: 'MRZ:FLORES | VIZ:FLOREZ',
        },
      },
    };

    render(<ExtractionDetails data={conflictResponse} onReset={vi.fn()} />);

    expect(
      screen.getByText(/Cross-Zone Reconciliation Discrepancy/i),
    ).toBeInTheDocument();
    expect(screen.getByText('Discrepancy Detected')).toBeInTheDocument();
    expect(screen.getAllByText('FLOREZ')[0]).toBeInTheDocument();
  });

  it('renders incomplete MRZ advisory banner when MRZ is detected without check digits', () => {
    const partialMrzResponse: PassportExtractionResponse = {
      ...mockResponse,
      mrz: {
        ...mockResponse.mrz,
        is_partial: true,
        partial_reason: 'single_line_detected',
        check_digits: [],
      },
    };

    render(<ExtractionDetails data={partialMrzResponse} onReset={vi.fn()} />);

    expect(
      screen.getByText(/Partial MRZ Zone Detected/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Check Digits Notice:/i),
    ).toBeInTheDocument();
  });
});

