export const ABOUT_ORGANIZATION_NODE_IDS = [
  "chairperson",
  "vice-chair",
  "secretariat",
  "secretary",
  "executive-committee",
  "voting-members",
  "non-voting-members",
  "special-non-voting",
  "sectoral-committees",
  "special-committees",
  "affiliate-committees",
  "advisory-committee",
] as const;

export type AboutOrganizationNodeId = (typeof ABOUT_ORGANIZATION_NODE_IDS)[number];

export const aboutNodeEditorLabel = (id: string) =>
  id
    .split("-")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
