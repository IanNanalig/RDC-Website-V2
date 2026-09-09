import { useEffect } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";

type Props = {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
};

const safeLink = (value: string) => /^(https?:\/\/|mailto:|\/|#)/i.test(value.trim());

const RichTextEditor = ({ value, onChange, disabled = false }: Props) => {
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [2, 3, 4] },
        code: false,
        codeBlock: false,
        horizontalRule: false,
        strike: false,
        link: {
          openOnClick: false,
          defaultProtocol: "https",
          protocols: ["http", "https", "mailto"],
        },
      }),
    ],
    content: value || "",
    editable: !disabled,
    immediatelyRender: false,
    onUpdate: ({ editor: currentEditor }) => {
      onChange(currentEditor.isEmpty ? "" : currentEditor.getHTML());
    },
  });

  useEffect(() => {
    if (!editor) return;
    editor.setEditable(!disabled);
  }, [disabled, editor]);

  useEffect(() => {
    if (!editor) return;
    const currentValue = editor.isEmpty ? "" : editor.getHTML();
    if (currentValue !== (value || "")) {
      editor.commands.setContent(value || "", { emitUpdate: false });
    }
  }, [editor, value]);

  if (!editor) {
    return <div className="cms-rich-editor-loading">Loading the article editor...</div>;
  }

  const setLink = () => {
    const current = String(editor.getAttributes("link").href || "");
    const entered = window.prompt("Enter a web address or email link", current);
    if (entered === null) return;
    const href = entered.trim();
    if (!href) {
      editor.chain().focus().extendMarkRange("link").unsetLink().run();
      return;
    }
    if (!safeLink(href)) {
      window.alert("Use a full http/https address, an email link, a page path beginning with /, or an anchor beginning with #.");
      return;
    }
    editor.chain().focus().extendMarkRange("link").setLink({ href }).run();
  };

  const toolbarButton = (label: string, active: boolean, action: () => void, disabledButton = false) => (
    <button
      key={label}
      type="button"
      className={`cms-rich-editor-button ${active ? "cms-rich-editor-button-active" : ""}`}
      aria-pressed={active}
      disabled={disabled || disabledButton}
      onClick={action}
    >
      {label}
    </button>
  );

  return (
    <div className={`cms-rich-editor ${disabled ? "cms-rich-editor-disabled" : ""}`}>
      <div className="cms-rich-editor-toolbar" role="toolbar" aria-label="Article formatting controls">
        {toolbarButton("Paragraph", editor.isActive("paragraph"), () => editor.chain().focus().setParagraph().run())}
        {toolbarButton("H2", editor.isActive("heading", { level: 2 }), () => editor.chain().focus().toggleHeading({ level: 2 }).run())}
        {toolbarButton("H3", editor.isActive("heading", { level: 3 }), () => editor.chain().focus().toggleHeading({ level: 3 }).run())}
        {toolbarButton("H4", editor.isActive("heading", { level: 4 }), () => editor.chain().focus().toggleHeading({ level: 4 }).run())}
        {toolbarButton("Bold", editor.isActive("bold"), () => editor.chain().focus().toggleBold().run())}
        {toolbarButton("Italic", editor.isActive("italic"), () => editor.chain().focus().toggleItalic().run())}
        {toolbarButton("Underline", editor.isActive("underline"), () => editor.chain().focus().toggleUnderline().run())}
        {toolbarButton("Bullets", editor.isActive("bulletList"), () => editor.chain().focus().toggleBulletList().run())}
        {toolbarButton("Numbered", editor.isActive("orderedList"), () => editor.chain().focus().toggleOrderedList().run())}
        {toolbarButton("Quote", editor.isActive("blockquote"), () => editor.chain().focus().toggleBlockquote().run())}
        {toolbarButton("Link", editor.isActive("link"), setLink)}
        {toolbarButton("Unlink", false, () => editor.chain().focus().unsetLink().run(), !editor.isActive("link"))}
        {toolbarButton("Undo", false, () => editor.chain().focus().undo().run(), !editor.can().undo())}
        {toolbarButton("Redo", false, () => editor.chain().focus().redo().run(), !editor.can().redo())}
      </div>
      <EditorContent editor={editor} />
      <p className="cms-rich-editor-help">Use the toolbar to format the article. Unsafe code and unsupported formatting are removed when content is published.</p>
    </div>
  );
};

export default RichTextEditor;
