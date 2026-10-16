import { type Metadata } from 'next';
import './globals.css';

// Typography is resolved from the system fallback stacks defined in globals.css
// (`--font-sans`, `--font-mono`, `--font-display`). We intentionally avoid `next/font/google`
// so the build has no network dependency on Google Fonts (which was intermittently
// unreachable and failed CI builds).

export const metadata: Metadata = {
  title: 'CloudNova PaymentOps',
  description:
    'CloudNova PaymentOps analyzes and reconciles payment data. It does not execute, authorize, settle, debit or credit payments.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
