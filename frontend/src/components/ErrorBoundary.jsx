import { Component } from 'react';

// Centralized client-side error reporter (BUG-3). Phase 4 wires this to the
// Sentry browser SDK; today it only logs. Routing reports through one seam keeps
// production users from ever seeing raw stack traces.
function reportError(error, info) {
  // eslint-disable-next-line no-console
  console.error('[ErrorBoundary]', error, info?.componentStack);
  // Phase 4: Sentry.captureException(error, { contexts: { react: info } });
}

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, stack: '' };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    reportError(error, info);
    // BUG-3: only retain the raw stack in development. In a production build
    // import.meta.env.DEV is false, so end users never see stack traces.
    if (import.meta.env.DEV) {
      this.setState({ stack: (error?.stack || '') + '\n---\n' + (info?.componentStack || '') });
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-[300px] p-8 text-center">
          <div className="text-4xl mb-4">😵</div>
          <h2 className="text-xl font-semibold text-gray-800 mb-2">Something went wrong</h2>
          <p className="text-gray-500 mb-4 max-w-md text-sm">
            {this.state.error?.message || 'An unexpected error occurred.'}
          </p>
          {import.meta.env.DEV && this.state.stack && (
            <pre className="text-left text-[10px] bg-gray-900 text-red-300 rounded-lg p-3 mb-4 max-w-2xl max-h-64 overflow-auto whitespace-pre-wrap">
              {this.state.stack}
            </pre>
          )}
          <div className="flex gap-3">
            <button
              onClick={this.handleReset}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
            >
              Try Again
            </button>
            <button
              onClick={() => window.location.href = '/'}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 text-sm"
            >
              Go Home
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
