@normal-font: 'Arial Regular';
@bold-font: 'Arial Bold';

#roads, #paths_track, #paths_euromat, #paths_fire_lane, #license_perimeter, #fence_heras, #fields {
    line-join: round;
    line-cap: round;
}

#roads {
    line-color: #888;
    line-width: 5;
    [zoom > 17] {
        line-width:8;
    }
}

#paths_track, #paths_euromat {
    line-color: #888;
    line-width: 4;
    [zoom > 17] {
        line-width:6;
    }
}

#paths_fire_lane {
    line-color: #bbb;
    line-width: 4;
    [zoom > 17] {
        line-width:6;
    }
}

#license_perimeter {
    line-color: #d00;
    line-width: 2;
}

#fence_heras {
    line-color: #000;
    line-width: 1;
}

#fields {
    line-color: #383;
    line-width: 1;
}

#labels, #tents, #installations, #buildings, #villages {
    text-name: "[text]";
    text-vertical-alignment: middle;
    text-horizontal-alignment: middle;
    text-halo-fill: rgba(255,255,255,0.7);
}

#labels {
    text-size: 14;
    text-face-name: @bold-font;
    text-halo-radius: 3;
}

#villages [zoom > 18] {
    text-size: 11;
    text-face-name: @normal-font;
    text-halo-radius: 1;
    text-wrap-width: 50;
    text-wrap-before: true;
}

#tents {
    [zoom > 17] {
        text-size: 11;
        text-color: #4E3F7C;
        text-face-name: @normal-font;
        text-halo-radius: 1;
        text-wrap-width: 50;
        text-wrap-before: true;
    }
    line-color: #4E3F7C;
    line-width: 1.5;
}

#tents[text=~ "(Stage .*|Lounge|Bar)"] {
    text-face-name: @bold-font;
    text-size: 14;
    text-halo-radius: 3;
}

#buildings {
    text-size: 11;
    text-face-name: @normal-font;
    text-halo-radius: 1;
    polygon-fill: #ddd;
}

#hardstanding {
    polygon-fill: #888;
}

#installations {
    line-color: #811453;
    line-width: 1;
    [zoom > 17] {
        text-name: "[text]";
        text-size: 11;
        text-face-name: @normal-font;
        text-halo-radius: 1;
        text-halo-fill: rgba(255,255,255,0.6);
    }
}

#showers {
    line-color: blue;
    line-width: 1;
}

#water_taps {
    marker-file: url(markers/water.svg);
    marker-fill: blue;
    marker-width: 25;
    marker-height: 25;
}

#trees {
    ::canopy {
    opacity: 0.3;
      marker-fill: green;
      marker-allow-overlap: true;
      marker-line-width: 0;
      marker-width: 5;
      marker-height: 5;
      marker-ignore-placement: true;
      [zoom >= 18] {
        marker-width: 15;
        marker-height: 15;
      }
      [zoom >= 19] {
        marker-width: 30;
        marker-height: 30;
      }
    }
    ::trunk {
    [zoom >= 18] {
      trunk/marker-fill: #b27f36;
      trunk/marker-allow-overlap: true;
      trunk/marker-line-width: 0;
      trunk/marker-width: 3;
      trunk/marker-height: 3;
      trunk/marker-ignore-placement: true;
    }
    [zoom >= 19] {
      trunk/marker-width: 6;
      trunk/marker-height: 6;
    }
  }
}

#woodland {
    polygon-fill: #add19e;
}

#areas_camping {
    polygon-fill: #D6F7D5;
    polygon-smooth: 0.1;
}

#toilets[text='WC'] {
    marker-file: url(markers/toilet.svg);
    marker-fill: blue;
    marker-width: 25;
    marker-height: 25;
}
