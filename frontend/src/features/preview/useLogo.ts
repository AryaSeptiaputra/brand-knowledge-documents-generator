import { skipToken, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type LogoInfo, removeLogo, uploadLogo } from "../../api/client";

const logoKey = (sessionId: string) => ["logo", sessionId] as const;
const previewKey = (sessionId: string) => ["preview", sessionId] as const;

export function useLogo(sessionId: string, onError: (message: string) => void) {
  const queryClient = useQueryClient();
  // The logo status is written by the upload and remove mutations, never fetched.
  const logo = useQuery<LogoInfo | null>({
    queryKey: logoKey(sessionId),
    queryFn: skipToken,
    staleTime: Number.POSITIVE_INFINITY,
  }).data;
  const upload = useMutation({
    mutationFn: (file: File) => uploadLogo(sessionId, file),
    onSuccess: async (info) => {
      queryClient.setQueryData(logoKey(sessionId), info);
      await queryClient.invalidateQueries({ queryKey: previewKey(sessionId) });
    },
    onError: (error) => onError(error.message),
  });
  const remove = useMutation({
    mutationFn: () => removeLogo(sessionId),
    onSuccess: async () => {
      queryClient.setQueryData(logoKey(sessionId), null);
      await queryClient.invalidateQueries({ queryKey: previewKey(sessionId) });
    },
    onError: (error) => onError(error.message),
  });
  return { logoName: logo?.file_name ?? null, upload, remove };
}
