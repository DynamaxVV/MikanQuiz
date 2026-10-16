/** Public site details, replaced by Vite at build time. Never put secrets here. */
export const site = {
  groupName: import.meta.env.VITE_SITE_GROUP_NAME?.trim() ?? '',
  groupDescription: import.meta.env.VITE_SITE_GROUP_DESCRIPTION?.trim() ?? '',
  joinGroup: import.meta.env.VITE_SITE_JOIN_GROUP?.trim() ?? '',
  chatGroup: import.meta.env.VITE_SITE_CHAT_GROUP?.trim() ?? '',
};
