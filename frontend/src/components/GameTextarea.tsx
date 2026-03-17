interface GameTextareaProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  maxLength: number;
  placeholder: string;
  autoFocus?: boolean;
}

export function GameTextarea({
  value,
  onChange,
  onSubmit,
  maxLength,
  placeholder,
  autoFocus,
}: GameTextareaProps) {
  return (
    <textarea
      value={value}
      onKeyDown={(e) => {
        if (e.key === "Enter" && !e.shiftKey) {
          e.preventDefault();
          onSubmit();
        }
      }}
      onChange={(e) => {
        onChange(e.target.value);
        e.target.style.height = "auto";
        e.target.style.height = e.target.scrollHeight + "px";
      }}
      maxLength={maxLength}
      rows={1}
      className="w-full resize-none border-b bg-transparent px-0 py-2 min-h-[44px] font-literary text-[1.05rem] leading-[1.6] text-ink outline-none border-rule"
      placeholder={placeholder}
      autoFocus={autoFocus}
    />
  );
}
