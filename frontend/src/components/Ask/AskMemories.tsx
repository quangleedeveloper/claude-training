import { zodResolver } from "@hookform/resolvers/zod"
import { useMutation } from "@tanstack/react-query"
import { useForm } from "react-hook-form"
import { z } from "zod"

import { type AskResponse, SearchService } from "@/client"
import { Badge } from "@/components/ui/badge"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { LoadingButton } from "@/components/ui/loading-button"
import useCustomToast from "@/hooks/useCustomToast"
import { handleError } from "@/utils"

const formSchema = z.object({
  question: z
    .string()
    .min(1, { message: "Ask something about your memories" })
    .max(500, { message: "Question must be at most 500 characters" }),
})

type FormData = z.infer<typeof formSchema>

const AskMemories = () => {
  const { showErrorToast } = useCustomToast()

  const form = useForm<FormData>({
    resolver: zodResolver(formSchema),
    defaultValues: { question: "" },
  })

  const mutation = useMutation({
    mutationFn: async (data: FormData): Promise<AskResponse> =>
      (await SearchService.askMemories({ body: data })).data,
    onError: handleError.bind(showErrorToast),
  })

  return (
    <div className="grid gap-6">
      <Form {...form}>
        <form
          className="flex items-start gap-2"
          onSubmit={form.handleSubmit((data) => mutation.mutate(data))}
        >
          <FormField
            control={form.control}
            name="question"
            render={({ field }) => (
              <FormItem className="flex-1">
                <FormLabel className="sr-only">Your question</FormLabel>
                <FormControl>
                  <Input
                    placeholder="Who taught Grandpa to fish?"
                    autoComplete="off"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <LoadingButton type="submit" loading={mutation.isPending}>
            Ask
          </LoadingButton>
        </form>
      </Form>

      {mutation.data && (
        <Card>
          <CardHeader>
            <CardTitle>Answer</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <p className="whitespace-pre-wrap">{mutation.data.answer}</p>
            {mutation.data.sources.length > 0 && (
              <div className="grid gap-2">
                <h3 className="text-sm font-semibold">Based on</h3>
                <ol className="grid gap-2" aria-label="Sources">
                  {mutation.data.sources.map((source, index) => (
                    <li
                      key={source.item.id}
                      className="rounded-md border p-3 text-sm"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <p>
                          <span className="font-medium">[{index + 1}]</span>{" "}
                          {source.item.content}
                        </p>
                        <Badge variant="secondary">
                          {Math.round(source.score * 100)}% match
                        </Badge>
                      </div>
                      <CardDescription className="mt-1">
                        {source.memory_title} · about {source.person_name}
                        {source.item.event_date_text &&
                          ` · ${source.item.event_date_text}`}
                      </CardDescription>
                    </li>
                  ))}
                </ol>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export default AskMemories
