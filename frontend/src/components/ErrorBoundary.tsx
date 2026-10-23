import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertOctagon, RefreshCw } from 'lucide-react';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Intentionally keep logging minimal without leaking sensitive data
    console.error('Unhandled React application exception:', error.message, errorInfo.componentStack);
  }

  handleReload = (): void => {
    window.location.reload();
  };

  handleReset = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="error-boundary-wrapper" role="alert" aria-live="assertive">
          <div className="error-boundary-card">
            <div className="error-boundary-icon">
              <AlertOctagon size={36} color="var(--color-error)" />
            </div>
            <h2 className="error-boundary-title">Application Interface Error</h2>
            <p className="error-boundary-desc">
              PassPortIQ encountered an unexpected client-side rendering exception. Your uploaded
              data was not compromised and remains transient in memory.
            </p>
            {this.state.error?.message && (
              <pre className="error-boundary-details">{this.state.error.message}</pre>
            )}
            <div className="error-boundary-actions">
              <button
                type="button"
                className="btn btn--primary"
                onClick={this.handleReset}
              >
                <RefreshCw size={14} />
                <span>Dismiss &amp; Return to Home</span>
              </button>
              <button
                type="button"
                className="btn btn--secondary"
                onClick={this.handleReload}
              >
                Reload Window
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
