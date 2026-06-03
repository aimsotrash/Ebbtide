import { Component, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="flex flex-col items-center justify-center p-8 glass-card text-center gap-4">
          <AlertTriangle className="text-destructive" size={36} />
          <div>
            <p className="text-foreground font-medium">Something went wrong</p>
            <p className="text-muted-foreground text-sm mt-1">{this.state.error?.message}</p>
          </div>
          <button
            className="btn-secondary flex items-center gap-2"
            onClick={() => this.setState({ hasError: false, error: undefined })}
          >
            <RefreshCw size={14} />
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
