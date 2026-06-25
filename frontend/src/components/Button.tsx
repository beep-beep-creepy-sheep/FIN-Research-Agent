type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement>;

export function Button({ className = "", ...props }: ButtonProps) {
  return (
    <button
      className={`rounded-md bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-teal-800 disabled:opacity-50 ${className}`}
      {...props}
    />
  );
}

