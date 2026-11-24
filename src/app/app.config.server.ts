import { mergeApplicationConfig, ApplicationConfig } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideServerRendering, withRoutes } from '@angular/ssr';
import { appConfig } from './app.config';
import { serverRoutes } from './app.routes.server';

const serverConfig: ApplicationConfig = {
  providers: [
    // Prerender route discovery needs a router even for a single page.
    provideRouter([]),
    provideServerRendering(withRoutes(serverRoutes))
  ]
};

export const config = mergeApplicationConfig(appConfig, serverConfig);
