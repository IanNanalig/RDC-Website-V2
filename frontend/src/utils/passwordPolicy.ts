const keyboardSymbols = "!\"#$%&'()*+,-./:;<=>?@[\\]^_\x60{|}~";

const hasKeyboardSymbol = (value: string) =>
  Array.from(value).some((character) => keyboardSymbols.includes(character));

export const passwordRules = [
  { label: "At least 12 characters", test: (v: string) => v.length >= 12 },
  { label: "At least 1 uppercase letter", test: (v: string) => /[A-Z]/.test(v) },
  { label: "At least 1 lowercase letter", test: (v: string) => /[a-z]/.test(v) },
  { label: "At least 1 number", test: (v: string) => /[0-9]/.test(v) },
  { label: "At least 1 symbol or special character", test: hasKeyboardSymbol },
];

export const validatePassword = (value: string) => {
  if (value.length < 12) return "Password must be at least 12 characters.";
  if (!/[A-Z]/.test(value)) return "Password must include an uppercase letter.";
  if (!/[a-z]/.test(value)) return "Password must include a lowercase letter.";
  if (!/[0-9]/.test(value)) return "Password must include a number.";
  if (!hasKeyboardSymbol(value)) return "Password must include a symbol.";
  return "";
};
