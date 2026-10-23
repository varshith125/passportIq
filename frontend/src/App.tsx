import React from 'react';
import { motion, AnimatePresence, useReducedMotion, type Variants } from 'framer-motion';
import { RefreshCw, FileUp, Cpu, CheckSquare2 } from 'lucide-react';
import { Header } from './components/Header';
import { UploadZone } from './components/UploadZone';
import { ProcessingBanner } from './components/ProcessingBanner';
import { PassportPreview } from './components/PassportPreview';
import { ExtractionDetails } from './components/ExtractionDetails';
import { usePassportScanner } from './features/scanner/usePassportScanner';

const isTestEnv =
  typeof import.meta !== 'undefined' &&
  (import.meta.env?.MODE === 'test' || Boolean(import.meta.env?.VITEST));

export const App: React.FC = () => {
  const shouldReduceMotion = useReducedMotion();
  const disableAnimation = Boolean(isTestEnv || shouldReduceMotion);

  const motionVariants: Variants = {
    initial: disableAnimation ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 },
    animate: {
      opacity: 1,
      y: 0,
      transition: { duration: disableAnimation ? 0 : 0.2, ease: [0.16, 1, 0.3, 1] },
    },
    exit: {
      opacity: 0,
      y: disableAnimation ? 0 : -6,
      transition: { duration: disableAnimation ? 0 : 0.15, ease: 'easeIn' },
    },
  };

  const {
    phase,
    selectedFile,
    result,
    errorCode,
    errorMessage,
    startExtraction,
    retryExtraction,
    resetScanner,
  } = usePassportScanner();

  return (
    <div className="app-shell">
      <Header />
      <main className="app-main">
        {/* Intro banner with workflow milestones — only displayed during upload */}
        {phase !== 'completed' && (
          <section className="intro-banner" aria-label="Tool overview">
            <div className="intro-banner__header">
              <div>
                <h2 className="intro-banner__title">
                  Intelligent Passport Data Extraction &amp; Verification
                </h2>
                <p className="intro-banner__desc">
                  Extract Machine Readable Zone (MRZ) &amp; Visible Inspection Zone (VIZ) data, verify ICAO 9303 Modulo-10 checksums, and detect cross-zone reconciliation discrepancies.
                </p>
              </div>
            </div>

            <div className="workflow-steps" aria-label="Processing workflow">
              <div className="workflow-step">
                <span className="workflow-step__num">1</span>
                <FileUp size={15} className="workflow-step__icon" aria-hidden="true" />
                <span><strong>Upload &amp; Inspect:</strong> Raw image decoded safely in-memory</span>
              </div>
              <div className="workflow-step">
                <span className="workflow-step__num">2</span>
                <Cpu size={15} className="workflow-step__icon" aria-hidden="true" />
                <span><strong>RapidOCR ONNX:</strong> Deep text recognition &amp; Mod-10 check digits</span>
              </div>
              <div className="workflow-step">
                <span className="workflow-step__num">3</span>
                <CheckSquare2 size={15} className="workflow-step__icon" aria-hidden="true" />
                <span><strong>Reconciliation:</strong> Provenance tracking &amp; conflict analysis</span>
              </div>
            </div>
          </section>
        )}

        <AnimatePresence mode="wait">
          {/* Upload Screen */}
          {(phase === 'idle' || (phase === 'error' && !result)) && (
            <motion.div
              key="upload-zone-wrapper"
              variants={motionVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              className="upload-wrapper"
            >
              {phase === 'error' && errorMessage && (
                <div
                  className="status-panel status-panel--error"
                  role="alert"
                  aria-live="assertive"
                  style={{ marginBottom: '1.25rem' }}
                >
                  <div>
                    <strong style={{ display: 'block', marginBottom: '0.25rem' }}>
                      Extraction Failed ({errorCode ?? 'ERROR'})
                    </strong>
                    <span>{errorMessage}</span>
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    {selectedFile && (
                      <button
                        type="button"
                        className="btn btn--primary"
                        onClick={retryExtraction}
                      >
                        <RefreshCw size={14} />
                        <span>Retry Extraction</span>
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn btn--secondary"
                      onClick={resetScanner}
                    >
                      Try Another File
                    </button>
                  </div>
                </div>
              )}

              <UploadZone
                disabled={false}
                onFileSelected={(file) => {
                  void startExtraction(file);
                }}
              />
            </motion.div>
          )}

          {/* Uploading / Processing State */}
          {phase === 'uploading' && selectedFile && (
            <motion.div
              key="processing-wrapper"
              variants={motionVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              className="processing-wrapper"
            >
              <ProcessingBanner
                fileName={selectedFile.name}
                onCancel={resetScanner}
              />

              {/* Show preview during processing so user sees their document immediately */}
              <div style={{ marginTop: '1.25rem', maxWidth: '640px', margin: '1.25rem auto 0' }}>
                <PassportPreview
                  file={selectedFile}
                  phase={phase}
                  onReplaceFile={(newFile) => {
                    void startExtraction(newFile);
                  }}
                />
              </div>
            </motion.div>
          )}

          {/* Completed State: Clean, Direct Two-Column Layout (Photo on Left, Extracted Details on Right) */}
          {phase === 'completed' && result && (
            <motion.div
              key="workspace-completed"
              variants={motionVariants}
              initial="initial"
              animate="animate"
              exit="exit"
              className="workspace-grid"
            >
              {/* Left Column: Clear Passport Photo & Controls */}
              <aside className="workspace-grid__left" aria-label="Original document preview">
                <PassportPreview
                  file={selectedFile}
                  phase={phase}
                  preprocessing={result.preprocessing}
                  onReplaceFile={(newFile) => {
                    void startExtraction(newFile);
                  }}
                />
              </aside>

              {/* Right Column: Clear Extracted Passport Details */}
              <section className="workspace-grid__right" aria-label="Extracted passport details">
                <ExtractionDetails data={result} onReset={resetScanner} defaultTechOpen={true} />
              </section>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
};

export default App;
