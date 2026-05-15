module Main exposing (main)

import Browser
import Browser.Navigation as Nav
import Dict exposing (Dict)
import Html exposing (Html, a, button, div, footer, h1, h2, header, input, label, li, main_, p, span, text, ul)
import Html.Attributes as A exposing (checked, class, href, placeholder, target, type_, value)
import Html.Events exposing (onCheck, onClick, onInput, onMouseLeave, onMouseOver)
import Http
import Json.Decode as D exposing (Decoder)
import Set exposing (Set)
import Svg exposing (Svg, circle, g, line, svg, text_)
import Svg.Attributes as SA
import Svg.Events as SE
import Url exposing (Url)
import Url.Builder as UB



-- MODEL ----------------------------------------------------------------------


type alias Source =
    { name : Maybe String
    , url : Maybe String
    , publisher : Maybe String
    }


type alias Risk =
    { slug : String
    , name : String
    , description : Maybe String
    , category : String
    , micromorts : Float
    , exposure : String
    , exposureDetail : Maybe String
    , population : Maybe String
    , region : Maybe String
    , year : Maybe Int
    , originalValue : Maybe String
    , originalUnit : Maybe String
    , confidence : Maybe String
    , notes : Maybe String
    , source : Source
    , tags : List String
    }


type alias Model =
    { state : LoadState
    , key : Nav.Key
    , path : String
    , query : String
    , categoryFilter : Set String
    , exposureFilter : Set String
    , hovered : Maybe String
    , selected : Maybe String
    , userSelected : Bool
    , scale : Scale
    }


type Scale
    = Linear
    | Log


type LoadState
    = Loading
    | Failed String
    | Loaded (List Risk)


init : () -> Url -> Nav.Key -> ( Model, Cmd Msg )
init _ url key =
    let
        p =
            parseUrl url
    in
    ( { state = Loading
      , key = key
      , path = url.path
      , query = p.query
      , categoryFilter = p.categories
      , exposureFilter = p.exposures
      , hovered = Nothing
      , selected = p.selected
      , userSelected = p.selected /= Nothing
      , scale = p.scale
      }
    , Http.get
        { url = "data.json"
        , expect = Http.expectJson GotData payloadDecoder
        }
    )


type alias UrlParams =
    { query : String
    , categories : Set String
    , exposures : Set String
    , scale : Scale
    , selected : Maybe String
    }


parseUrl : Url -> UrlParams
parseUrl url =
    let
        pairs : Dict String String
        pairs =
            url.query
                |> Maybe.withDefault ""
                |> String.split "&"
                |> List.filterMap parsePair
                |> Dict.fromList

        getSet key =
            case Dict.get key pairs of
                Just raw ->
                    raw
                        |> String.split ","
                        |> List.filter (not << String.isEmpty)
                        |> Set.fromList

                Nothing ->
                    Set.empty
    in
    { query = Dict.get "q" pairs |> Maybe.withDefault ""
    , categories = getSet "cat"
    , exposures = getSet "exp"
    , scale =
        if Dict.get "scale" pairs == Just "log" then
            Log

        else
            Linear
    , selected = Dict.get "sel" pairs
    }


parsePair : String -> Maybe ( String, String )
parsePair s =
    case String.split "=" s of
        [ k, v ] ->
            case Url.percentDecode v of
                Just decoded ->
                    Just ( k, decoded )

                Nothing ->
                    Nothing

        _ ->
            Nothing


buildUrl : Model -> String
buildUrl m =
    let
        joined s =
            s |> Set.toList |> String.join ","

        params =
            List.filterMap identity
                [ if String.isEmpty m.query then
                    Nothing

                  else
                    Just (UB.string "q" m.query)
                , if Set.isEmpty m.categoryFilter then
                    Nothing

                  else
                    Just (UB.string "cat" (joined m.categoryFilter))
                , if Set.isEmpty m.exposureFilter then
                    Nothing

                  else
                    Just (UB.string "exp" (joined m.exposureFilter))
                , if m.scale == Log then
                    Just (UB.string "scale" "log")

                  else
                    Nothing
                , if m.userSelected then
                    Maybe.map (UB.string "sel") m.selected

                  else
                    Nothing
                ]

    in
    m.path ++ UB.toQuery params


syncUrl : Model -> Cmd Msg
syncUrl m =
    Nav.replaceUrl m.key (buildUrl m)



-- DECODERS -------------------------------------------------------------------


payloadDecoder : Decoder (List Risk)
payloadDecoder =
    D.field "risks" (D.list riskDecoder)


nullable : String -> Decoder a -> Decoder (Maybe a)
nullable name dec =
    D.field name (D.nullable dec)


riskDecoder : Decoder Risk
riskDecoder =
    D.map8 Risk
        (D.field "slug" D.string)
        (D.field "name" D.string)
        (nullable "description" D.string)
        (D.field "category" D.string)
        (D.field "micromorts" D.float)
        (D.field "exposure" D.string)
        (nullable "exposureDetail" D.string)
        (nullable "population" D.string)
        |> andMap (nullable "region" D.string)
        |> andMap (nullable "year" D.int)
        |> andMap (nullable "originalValue" D.string)
        |> andMap (nullable "originalUnit" D.string)
        |> andMap (nullable "confidence" D.string)
        |> andMap (nullable "notes" D.string)
        |> andMap (D.field "source" sourceDecoder)
        |> andMap (D.field "tags" (D.list D.string))


andMap : Decoder a -> Decoder (a -> b) -> Decoder b
andMap =
    D.map2 (|>)


sourceDecoder : Decoder Source
sourceDecoder =
    D.map3 Source
        (D.maybe (D.field "name" D.string))
        (D.maybe (D.field "url" D.string))
        (D.maybe (D.field "publisher" D.string))



-- UPDATE ---------------------------------------------------------------------


type Msg
    = GotData (Result Http.Error (List Risk))
    | QueryChanged String
    | ToggleCategory String Bool
    | ToggleExposure String Bool
    | Hover (Maybe String)
    | Select (Maybe String)
    | ClearFilters
    | SetScale Scale
    | UrlChanged Url
    | LinkClicked Browser.UrlRequest


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        GotData (Ok rs) ->
            let
                m2 =
                    { model
                        | state = Loaded rs
                        , selected =
                            case model.selected of
                                Just _ ->
                                    model.selected

                                Nothing ->
                                    defaultSelection rs
                    }
            in
            ( m2, Cmd.none )

        GotData (Err e) ->
            ( { model | state = Failed (httpError e) }, Cmd.none )

        QueryChanged q ->
            withUrl { model | query = q }

        ToggleCategory c on ->
            withUrl
                { model
                    | categoryFilter =
                        if on then
                            Set.insert c model.categoryFilter

                        else
                            Set.remove c model.categoryFilter
                }

        ToggleExposure e on ->
            withUrl
                { model
                    | exposureFilter =
                        if on then
                            Set.insert e model.exposureFilter

                        else
                            Set.remove e model.exposureFilter
                }

        Hover slug ->
            ( { model | hovered = slug }, Cmd.none )

        Select slug ->
            withUrl
                { model
                    | selected = slug
                    , userSelected = slug /= Nothing
                }

        ClearFilters ->
            withUrl
                { model
                    | query = ""
                    , categoryFilter = Set.empty
                    , exposureFilter = Set.empty
                }

        SetScale s ->
            withUrl { model | scale = s }

        UrlChanged _ ->
            ( model, Cmd.none )

        LinkClicked req ->
            case req of
                Browser.Internal _ ->
                    ( model, Cmd.none )

                Browser.External href ->
                    ( model, Nav.load href )


withUrl : Model -> ( Model, Cmd Msg )
withUrl m =
    ( m, syncUrl m )


defaultSelection : List Risk -> Maybe String
defaultSelection rs =
    let
        preferred =
            [ "wiki:baseline-all-causes-us-day"
            , "wiki:baseline-all-causes-eaw-day"
            , "background-mortality-uk-avg-day"
            ]

        findSlug slug =
            List.filter (\r -> r.slug == slug) rs
                |> List.head
                |> Maybe.map .slug
    in
    preferred
        |> List.filterMap findSlug
        |> List.head


httpError : Http.Error -> String
httpError e =
    case e of
        Http.BadUrl u ->
            "bad url: " ++ u

        Http.Timeout ->
            "request timed out"

        Http.NetworkError ->
            "network error"

        Http.BadStatus s ->
            "HTTP " ++ String.fromInt s

        Http.BadBody b ->
            "bad body: " ++ b



-- VIEW -----------------------------------------------------------------------


view : Model -> Html Msg
view model =
    main_ [ class "app" ]
        [ header [ class "topbar" ]
            [ h1 [] [ text "Micromort risk visualizer" ]
            , p [ class "subtitle" ]
                [ text "1 micromort = a one-in-a-million chance of death. "
                , text "Every entry has been normalized to micromorts; click a dot for details."
                ]
            ]
        , case model.state of
            Loading ->
                div [ class "placeholder" ] [ text "loading data…" ]

            Failed e ->
                div [ class "placeholder error" ]
                    [ text ("Couldn't load data.json: " ++ e) ]

            Loaded risks ->
                viewLoaded model risks
        , footer [ class "footer" ]
            [ text "Sources: Wikipedia (Micromort), NHTSA FARS, CDC NCHS, BLS CFOI, Howard 1979, Blastland & Spiegelhalter."
            ]
        ]


viewLoaded : Model -> List Risk -> Html Msg
viewLoaded model risks =
    let
        allCategories =
            uniqueSorted (List.map .category risks)

        allExposures =
            uniqueSorted (List.map .exposure risks)

        filtered =
            applyFilters model risks
    in
    div [ class "layout" ]
        [ div [ class "sidebar" ]
            [ input
                [ type_ "search"
                , placeholder "search name / tag / source…"
                , value model.query
                , onInput QueryChanged
                , class "search"
                ]
                []
            , scaleToggle model.scale
            , filterGroup "Category" model.categoryFilter ToggleCategory allCategories
            , filterGroup "Exposure" model.exposureFilter ToggleExposure allExposures
            , button [ class "clear", onClick ClearFilters ] [ text "Clear filters" ]
            , div [ class "count" ]
                [ text (String.fromInt (List.length filtered) ++ " of " ++ String.fromInt (List.length risks) ++ " risks") ]
            ]
        , div [ class "content" ]
            [ chart model filtered
            , detailPanel model risks
            , listView filtered
            ]
        ]


scaleToggle : Scale -> Html Msg
scaleToggle current =
    div [ class "filter-group scale-toggle" ]
        [ h2 [] [ text "Scale" ]
        , div [ class "seg" ]
            [ button
                [ class
                    ("seg-btn"
                        ++ (if current == Linear then
                                " active"

                            else
                                ""
                           )
                    )
                , onClick (SetScale Linear)
                ]
                [ text "linear" ]
            , button
                [ class
                    ("seg-btn"
                        ++ (if current == Log then
                                " active"

                            else
                                ""
                           )
                    )
                , onClick (SetScale Log)
                ]
                [ text "log" ]
            ]
        ]


filterGroup : String -> Set String -> (String -> Bool -> Msg) -> List String -> Html Msg
filterGroup title selected toMsg options =
    div [ class "filter-group" ]
        [ h2 [] [ text title ]
        , ul []
            (List.map
                (\opt ->
                    li []
                        [ label []
                            [ input
                                [ type_ "checkbox"
                                , checked (Set.member opt selected)
                                , onCheck (toMsg opt)
                                ]
                                []
                            , span [ class ("badge cat-" ++ opt) ] [ text opt ]
                            ]
                        ]
                )
                options
            )
        ]


applyFilters : Model -> List Risk -> List Risk
applyFilters m risks =
    let
        q =
            String.toLower (String.trim m.query)

        matchesQuery r =
            if q == "" then
                True

            else
                let
                    hay =
                        String.toLower
                            (String.join " "
                                [ r.name
                                , r.category
                                , r.exposure
                                , Maybe.withDefault "" r.exposureDetail
                                , Maybe.withDefault "" r.population
                                , Maybe.withDefault "" r.region
                                , Maybe.withDefault "" r.notes
                                , Maybe.withDefault "" r.source.name
                                , String.join " " r.tags
                                ]
                            )
                in
                String.contains q hay

        matchesCategory r =
            Set.isEmpty m.categoryFilter || Set.member r.category m.categoryFilter

        matchesExposure r =
            Set.isEmpty m.exposureFilter || Set.member r.exposure m.exposureFilter
    in
    risks
        |> List.filter (\r -> matchesQuery r && matchesCategory r && matchesExposure r)



-- CHART ----------------------------------------------------------------------


chartWidth : Float
chartWidth =
    900


padLeft : Float
padLeft =
    100


padRight : Float
padRight =
    20


padTop : Float
padTop =
    30


padBottom : Float
padBottom =
    40


rowHeight : Float
rowHeight =
    30


type alias Axis =
    { scale : Scale
    , maxVal : Float
    , minVal : Float
    , ticks : List Float
    }


buildAxis : Scale -> List Risk -> Axis
buildAxis scale risks =
    let
        values =
            List.map .micromorts risks

        rawMax =
            List.maximum values |> Maybe.withDefault 1

        rawMin =
            List.minimum values |> Maybe.withDefault 0

        safeMax =
            if rawMax <= 0 then
                1

            else
                rawMax
    in
    case scale of
        Linear ->
            let
                upper =
                    niceCeiling safeMax

                ticks =
                    linearTicks 0 upper 6
            in
            { scale = scale, maxVal = upper, minVal = 0, ticks = ticks }

        Log ->
            let
                maxExp =
                    toFloat (ceiling (logBase 10 (max 1.0e-9 safeMax)))

                minExp =
                    toFloat (floor (logBase 10 (max 1.0e-9 rawMin)))

                lo =
                    min (minExp) (maxExp - 1)

                hi =
                    max maxExp (lo + 1)
            in
            { scale = scale
            , maxVal = 10 ^ hi
            , minVal = 10 ^ lo
            , ticks = List.map (\e -> 10 ^ toFloat e) (List.range (round lo) (round hi))
            }


niceCeiling : Float -> Float
niceCeiling x =
    if x <= 0 then
        1

    else
        let
            e =
                toFloat (floor (logBase 10 x))

            f =
                x / (10 ^ e)

            niceF =
                if f <= 1 then
                    1

                else if f <= 2 then
                    2

                else if f <= 2.5 then
                    2.5

                else if f <= 5 then
                    5

                else
                    10
        in
        niceF * (10 ^ e)


linearTicks : Float -> Float -> Int -> List Float
linearTicks lo hi target =
    let
        step =
            niceStep ((hi - lo) / toFloat target)

        first =
            toFloat (ceiling (lo / step)) * step

        go acc v =
            if v > hi + step / 2 then
                List.reverse acc

            else
                go (v :: acc) (v + step)
    in
    go [] first


niceStep : Float -> Float
niceStep raw =
    if raw <= 0 then
        1

    else
        let
            e =
                toFloat (floor (logBase 10 raw))

            f =
                raw / (10 ^ e)

            niceF =
                if f < 1.5 then
                    1

                else if f < 3 then
                    2

                else if f < 7 then
                    5

                else
                    10
        in
        niceF * (10 ^ e)


xForMicromorts : Axis -> Float -> Float
xForMicromorts axis mm =
    let
        usable =
            chartWidth - padLeft - padRight
    in
    case axis.scale of
        Linear ->
            let
                clamped =
                    clamp 0 axis.maxVal mm

                f =
                    if axis.maxVal == 0 then
                        0

                    else
                        clamped / axis.maxVal
            in
            padLeft + f * usable

        Log ->
            let
                e =
                    logBase 10 (max 1.0e-12 mm)

                lo =
                    logBase 10 axis.minVal

                hi =
                    logBase 10 axis.maxVal

                clamped =
                    clamp lo hi e

                f =
                    if hi == lo then
                        0

                    else
                        (clamped - lo) / (hi - lo)
            in
            padLeft + f * usable


chart : Model -> List Risk -> Svg Msg
chart model risks =
    let
        rows =
            List.map (categoryRow model risks) (uniqueSorted (List.map .category risks))

        nRows =
            max 1 (List.length rows)

        chartHeight =
            padTop + padBottom + rowHeight * toFloat nRows

        axis =
            buildAxis model.scale risks
    in
    div [ class "chart-wrap" ]
        [ svg
            [ SA.viewBox ("0 0 " ++ String.fromFloat chartWidth ++ " " ++ String.fromFloat chartHeight)
            , SA.class "chart"
            ]
            (xAxis axis chartHeight :: rowYLabelsAndDots model axis rows chartHeight)
        ]


rowYLabelsAndDots : Model -> Axis -> List ( String, List Risk ) -> Float -> List (Svg Msg)
rowYLabelsAndDots model axis rows chartHeight =
    List.concat
        (List.indexedMap
            (\i ( cat, rs ) ->
                let
                    y =
                        padTop + (toFloat i + 0.5) * rowHeight
                in
                text_
                    [ SA.x (String.fromFloat (padLeft - 10))
                    , SA.y (String.fromFloat (y + 4))
                    , SA.class ("row-label cat-" ++ cat)
                    , SA.textAnchor "end"
                    ]
                    [ Svg.text cat ]
                    :: List.map (dot model axis y) rs
            )
            rows
        )


categoryRow : Model -> List Risk -> String -> ( String, List Risk )
categoryRow _ risks cat =
    ( cat, List.filter (\r -> r.category == cat) risks )


dot : Model -> Axis -> Float -> Risk -> Svg Msg
dot model axis y r =
    let
        cx =
            xForMicromorts axis r.micromorts

        isHovered =
            model.hovered == Just r.slug

        isSelected =
            model.selected == Just r.slug
    in
    circle
        [ SA.cx (String.fromFloat cx)
        , SA.cy (String.fromFloat y)
        , SA.r
            (if isHovered || isSelected then
                "8"

             else
                "5"
            )
        , SA.class
            ("dot cat-"
                ++ r.category
                ++ (if isSelected then
                        " selected"

                    else
                        ""
                   )
            )
        , SE.onMouseOver (Hover (Just r.slug))
        , SE.onMouseOut (Hover Nothing)
        , SE.onClick (Select (Just r.slug))
        ]
        [ Svg.title [] [ Svg.text (r.name ++ "  —  " ++ formatMicromorts r.micromorts ++ " µmt " ++ humanizeExposure r.exposure) ] ]


xAxis : Axis -> Float -> Svg msg
xAxis axis chartHeight =
    let
        axisY =
            chartHeight - padBottom + 8

        scaleLabel =
            case axis.scale of
                Linear ->
                    "micromorts per exposure (linear)"

                Log ->
                    "micromorts per exposure (log scale)"
    in
    g [ SA.class "axis" ]
        (line
            [ SA.x1 (String.fromFloat padLeft)
            , SA.x2 (String.fromFloat (chartWidth - padRight))
            , SA.y1 (String.fromFloat axisY)
            , SA.y2 (String.fromFloat axisY)
            , SA.class "axis-line"
            ]
            []
            :: List.concatMap (tickGroup axis chartHeight) axis.ticks
            ++ [ text_
                    [ SA.x (String.fromFloat ((padLeft + chartWidth - padRight) / 2))
                    , SA.y "18"
                    , SA.class "axis-title"
                    , SA.textAnchor "middle"
                    ]
                    [ Svg.text scaleLabel ]
               ]
        )


tickGroup : Axis -> Float -> Float -> List (Svg msg)
tickGroup axis chartHeight value =
    let
        x =
            xForMicromorts axis value

        axisY =
            chartHeight - padBottom + 8

        label =
            case axis.scale of
                Log ->
                    let
                        e =
                            round (logBase 10 value)
                    in
                    "10" ++ superscript e

                Linear ->
                    formatTickValue value
    in
    [ line
        [ SA.x1 (String.fromFloat x)
        , SA.x2 (String.fromFloat x)
        , SA.y1 (String.fromFloat (axisY - 4))
        , SA.y2 (String.fromFloat (axisY + 4))
        , SA.class "axis-tick"
        ]
        []
    , text_
        [ SA.x (String.fromFloat x)
        , SA.y (String.fromFloat (axisY + 20))
        , SA.class "axis-label"
        , SA.textAnchor "middle"
        ]
        [ Svg.text label ]
    ]


superscript : Int -> String
superscript n =
    let
        digit d =
            case d of
                '0' ->
                    "⁰"

                '1' ->
                    "¹"

                '2' ->
                    "²"

                '3' ->
                    "³"

                '4' ->
                    "⁴"

                '5' ->
                    "⁵"

                '6' ->
                    "⁶"

                '7' ->
                    "⁷"

                '8' ->
                    "⁸"

                '9' ->
                    "⁹"

                '-' ->
                    "⁻"

                _ ->
                    ""
    in
    String.fromInt n
        |> String.toList
        |> List.map digit
        |> String.concat


formatTickValue : Float -> String
formatTickValue v =
    if v >= 1000 then
        let
            k =
                v / 1000
        in
        if k >= 100 then
            formatInt (round k) ++ "k"

        else if k == toFloat (round k) then
            String.fromInt (round k) ++ "k"

        else
            toFixed 1 k ++ "k"

    else if v >= 1 then
        if v == toFloat (round v) then
            String.fromInt (round v)

        else
            toFixed 1 v

    else
        toFixed 2 v



-- DETAIL ---------------------------------------------------------------------


detailPanel : Model -> List Risk -> Html Msg
detailPanel model risks =
    let
        focus =
            case ( model.selected, model.hovered ) of
                ( Just s, _ ) ->
                    findBy s risks

                ( _, Just h ) ->
                    findBy h risks

                _ ->
                    Nothing
    in
    case focus of
        Nothing ->
            div [ class "detail empty" ]
                [ text "Hover or click a dot to see details." ]

        Just r ->
            div [ class "detail" ]
                [ h2 [] [ text r.name ]
                , p [ class "headline" ]
                    [ span [ class "big" ] [ text (formatMicromorts r.micromorts) ]
                    , text " µmt "
                    , span [ class "muted" ] [ text (humanizeExposure r.exposure) ]
                    ]
                , p []
                    [ span [ class ("badge cat-" ++ r.category) ] [ text r.category ]
                    , text " · "
                    , text (humanizeExposure r.exposure)
                    , case r.year of
                        Just y ->
                            text (" · " ++ String.fromInt y)

                        Nothing ->
                            text ""
                    , case r.region of
                        Just rg ->
                            text (" · " ++ rg)

                        Nothing ->
                            text ""
                    ]
                , maybeP "Detail: " r.exposureDetail
                , maybeP "Population: " r.population
                , maybeP "Original: " r.originalValue
                , maybeP "Notes: " r.notes
                , viewTags r.tags
                , viewSource r.source
                ]


maybeP : String -> Maybe String -> Html msg
maybeP prefix m =
    case m of
        Just s ->
            p [ class "muted small" ] [ text (prefix ++ s) ]

        Nothing ->
            text ""


viewTags : List String -> Html msg
viewTags ts =
    if List.isEmpty ts then
        text ""

    else
        p [ class "tags" ]
            (List.map (\t -> span [ class "tag" ] [ text t ]) ts)


viewSource : Source -> Html msg
viewSource s =
    case s.url of
        Just u ->
            p [ class "small" ]
                [ text "Source: "
                , a [ href u, target "_blank" ]
                    [ text (Maybe.withDefault u s.name) ]
                ]

        Nothing ->
            case s.name of
                Just n ->
                    p [ class "small" ] [ text ("Source: " ++ n) ]

                Nothing ->
                    text ""


findBy : String -> List Risk -> Maybe Risk
findBy slug =
    List.filter (\r -> r.slug == slug) >> List.head


listView : List Risk -> Html Msg
listView risks =
    let
        items =
            risks
                |> List.sortBy .micromorts
                |> List.map row
    in
    div [ class "list" ]
        [ h2 [] [ text "All risks (ascending)" ]
        , ul [] items
        ]


row : Risk -> Html Msg
row r =
    li [ class "risk-row", onMouseOver (Hover (Just r.slug)), onClick (Select (Just r.slug)) ]
        [ span [ class "mm" ] [ text (formatMicromorts r.micromorts) ]
        , span [ class "mm-unit" ] [ text "µmt" ]
        , span [ class ("badge cat-" ++ r.category) ] [ text r.category ]
        , span [ class "exp" ] [ text (humanizeExposure r.exposure) ]
        , span [ class "name" ] [ text r.name ]
        ]



-- HELPERS --------------------------------------------------------------------


uniqueSorted : List String -> List String
uniqueSorted xs =
    xs |> Set.fromList |> Set.toList


humanizeExposure : String -> String
humanizeExposure e =
    case e of
        "per_event" ->
            "per event"

        "per_year" ->
            "per year"

        "per_day" ->
            "per day"

        "per_hour" ->
            "per hour"

        "per_mile" ->
            "per mile"

        "per_km" ->
            "per km"

        "per_trip" ->
            "per trip"

        "per_jump" ->
            "per jump"

        "per_dive" ->
            "per dive"

        "per_climb" ->
            "per climb"

        "lifetime" ->
            "lifetime"

        _ ->
            String.replace "_" " " e


formatMicromorts : Float -> String
formatMicromorts m =
    if m >= 1000 then
        formatInt (round m)

    else if m >= 10 then
        toFixed 1 m

    else if m >= 1 then
        toFixed 2 m

    else if m >= 0.01 then
        toFixed 3 m

    else
        toFixed 5 m


toFixed : Int -> Float -> String
toFixed n x =
    let
        mult =
            toFloat (10 ^ n)

        rounded =
            toFloat (round (x * mult)) / mult

        s =
            String.fromFloat rounded
    in
    case String.split "." s of
        [ a ] ->
            if n == 0 then
                a

            else
                a ++ "." ++ String.repeat n "0"

        [ a, b ] ->
            if String.length b >= n then
                a ++ "." ++ String.left n b

            else
                a ++ "." ++ b ++ String.repeat (n - String.length b) "0"

        _ ->
            s


formatInt : Int -> String
formatInt n =
    let
        s =
            String.fromInt (abs n)

        grouped =
            s
                |> String.toList
                |> List.reverse
                |> List.indexedMap
                    (\i c ->
                        if i > 0 && modBy 3 i == 0 then
                            String.fromList [ c, ',' ]

                        else
                            String.fromChar c
                    )
                |> List.reverse
                |> String.concat
    in
    if n < 0 then
        "-" ++ grouped

    else
        grouped



-- MAIN -----------------------------------------------------------------------


main : Program () Model Msg
main =
    Browser.application
        { init = init
        , update = update
        , subscriptions = always Sub.none
        , view = \m -> { title = "Micromort risk visualizer", body = [ view m ] }
        , onUrlRequest = LinkClicked
        , onUrlChange = UrlChanged
        }
