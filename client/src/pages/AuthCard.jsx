import { Logo } from "../components/Layout";

export default function AuthCard({ title, children, footer }) {
  return (
    <div className="grid min-h-screen place-items-center px-4 py-10">
      <div className="w-full max-w-sm animate-fade-in">
        <div className="mb-8 flex justify-center">
          <Logo />
        </div>
        <div className="tile glow glow-strong p-6">
          <h1 className="mb-5 text-lg font-semibold text-zinc-100">{title}</h1>
          {children}
        </div>
        {footer && <div className="mt-4 text-center text-sm text-zinc-500">{footer}</div>}
      </div>
    </div>
  );
}
