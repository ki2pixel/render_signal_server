### **Trigger deploy**

`POST` https://api.render.com/v1/services/{serviceId}/deploys

Trigger a deploy for the service with the provided ID.

---

#### **Path Params**

*   **serviceId** `string` `REQUIRED`
    The ID of the service.

---

#### **Body Params**

*   **clearCache** `string` `enum`
    Defaults to: `do_not_clear`
    If `clear`, Render clears the service's build cache before deploying. This can be useful if you're experiencing issues with your build.
    Allowed: `clear`, `do_not_clear`

*   **commitId** `string`
    The SHA of a specific Git commit to deploy for a service. Defaults to the latest commit on the service's connected branch.
    Note that deploying a specific commit with this endpoint does not disable autodeploys for the service.
    You can toggle autodeploys for your service with the Update service endpoint or in the Render Dashboard.
    Not supported for cron jobs.

*   **imageUrl** `string`
    The URL of the image to deploy for an image-backed service.
    The host, repository, and image name all must match the currently configured image for the service.

---

#### **Responses**

*   **201 Created**
    ##### **RESPONSE BODY**
    *   **object**
        *   **id** `string` `REQUIRED`
        *   **commit** `object`
            *   **id** `string`
            *   **message** `string`
            *   **createdAt** `date-time`
        *   **image** `object`
            Image information used when creating the deploy. Not present for Git-backed deploys
            *   **ref** `string`
                Image reference used when creating the deploy
            *   **sha** `string`
                SHA that the image reference was resolved to when creating the deploy
            *   **registryCredential** `string`
                Name of credential used to pull the image, if provided.
        *   **status** `string` `enum`
            `created`, `queued`, `build_in_progress`, `update_in_progress`, `live`, `deactivated`, `build_failed`, `update_failed`, `canceled`, `pre_deploy_in_progress`, `pre_deploy_failed`
        *   **trigger** `string` `enum`
            `api`, `blueprint_sync`, `deploy_hook`, `deployed_by_render`, `manual`, `other`, `new_commit`, `rollback`, `service_resumed`, `service_updated`
        *   **startedAt** `date-time`
        *   **finishedAt** `date-time`
        *   **createdAt** `date-time`
        *   **updatedAt** `date-time`

*   **202 Queued**

*   **400 The request could not be understood by the server.**

*   **401 Authorization information is missing or invalid.**

*   **404 Unable to find the requested resource.**

*   **406 Unable to generate preferred media types as specified by Accept request header.**

*   **409 The current state of the resource conflicts with this request.**

*   **410 The requested resource is no longer available.**

*   **429 Rate limit has been surpassed.**

*   **500 An unexpected server error has occurred.**

*   **503 Server currently unavailable.**