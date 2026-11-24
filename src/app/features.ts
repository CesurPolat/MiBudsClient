import {ChangeDetectionStrategy, Component} from '@angular/core';
@Component({selector:'app-features', templateUrl:'./features.html', styleUrl:'./features.css', changeDetection:ChangeDetectionStrategy.OnPush})
export class Features {
  protected readonly levels = [14,22,32,25,15,25,33,43,34,26,16,22,31,40,48,38,29,19,14,22,30,23,16,12];
}
