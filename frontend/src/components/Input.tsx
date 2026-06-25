type InputProps = React.InputHTMLAttributes<HTMLInputElement>;

export function Input({ className = "", ...props }: InputProps) {
  return (
    <input
      className={`rounded-md border border-line bg-white px-3 py-2 text-sm outline-none focus:border-accent ${className}`}
      {...props}
    />
  );
}

